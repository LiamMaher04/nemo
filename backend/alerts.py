"""Carer alerts: text the carer through the notifier (Photon), and record it in Spacetime.

notify(type, message) only calls the notifier. send_carer_alert(type, message) calls it AND writes
the alert to Spacetime's alerts table (channel "carer", sent true/false).

sender_loop() runs with the FastAPI app: Spacetime's check_alerts decides WHEN to alert (it writes
unsent rows to alerts); this loop just texts them and marks them sent.
"""

import asyncio
import logging
import time
from typing import Any

import httpx

from backend import settings
from backend import spacetime_client as st

log = logging.getLogger("nemo.alerts")


def notify(type: str, message: str) -> tuple[bool, str]:
    """POST the alert to the notifier. Returns (ok, error). Never raises.

    With CARER_ALERTS=off this never contacts the notifier, so nothing is ever texted.
    """
    if not settings.CARER_ALERTS:
        log.info("CARER_ALERTS is off: not texting %s (%r)", type, message)
        return False, "CARER_ALERTS is off"
    try:
        r = httpx.post(f"{settings.NOTIFIER_URL}/alert", json={"type": type, "message": message}, timeout=30.0)
        body = r.json()
    except Exception as exc:  # notifier not running, timed out, or replied with non-JSON
        return False, f"notifier unreachable: {exc}"
    if r.status_code == 200 and body.get("ok"):
        return True, ""
    return False, str(body.get("error") or f"HTTP {r.status_code}")


def send_carer_alert(type: str, message: str, item_id: str = "") -> dict[str, Any]:
    """Text the carer and record the alert in Spacetime, sent or not."""
    started = time.perf_counter()
    ok, error = notify(type, message)
    st.call("record_alert", type, item_id, message, "carer", time.time() * 1000, ok)
    ms = round((time.perf_counter() - started) * 1000)
    if ok:
        log.info("carer alert %s sent in %d ms", type, ms)
    else:
        log.warning("carer alert %s NOT sent (%s)", type, error)
    return {"sent": ok, "error": error, "ms": ms}


# ---- Sender loop for alerts raised inside Spacetime ----

SEND_EVERY_S = 5
MAX_TRIES = 3

_tries: dict[int, int] = {}  # alert id -> failed sends so far (resets when the backend restarts)


def send_pending_once() -> int:
    """Text every unsent carer alert once. Returns how many were sent."""
    sent = 0
    for a in st.sql("SELECT * FROM alerts WHERE channel = 'carer' AND sent = false"):
        alert_id = int(a["id"])
        if _tries.get(alert_id, 0) >= MAX_TRIES:
            continue  # gave up; it stays unsent so nothing new of that type is raised until it's cleared
        ok, error = notify(a["type"], a["message"])
        if ok:
            st.call("mark_alert_sent", alert_id, True)
            _tries.pop(alert_id, None)
            sent += 1
            log.info("alert #%d %s texted to the carer", alert_id, a["type"])
        else:
            _tries[alert_id] = _tries.get(alert_id, 0) + 1
            left = MAX_TRIES - _tries[alert_id]
            log.warning("alert #%d %s not sent (%s); %s", alert_id, a["type"], error,
                        f"{left} tries left" if left else "giving up")
    return sent


async def sender_loop() -> None:
    """Every SEND_EVERY_S seconds, text any unsent carer alerts. Runs until cancelled.

    With CARER_ALERTS=off it doesn't run at all: alerts raised in Spacetime stay unsent (and are
    cleared by reset_memory), so turning it back on can send any that are still waiting.
    """
    if not settings.CARER_ALERTS:
        log.info("CARER_ALERTS is off: the alert sender is not running (no texts)")
        return
    log.info("alert sender running every %d s", SEND_EVERY_S)
    while True:
        try:
            await asyncio.to_thread(send_pending_once)
        except Exception as exc:  # Spacetime unreachable etc: try again next round
            log.warning("alert sender round failed: %s", exc)
        await asyncio.sleep(SEND_EVERY_S)

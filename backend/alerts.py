"""Carer alerts: text the carer through the notifier (Photon), and record it in Spacetime.

notify(type, message) only calls the notifier. send_carer_alert(type, message) calls it AND writes
the alert to Spacetime's alerts table (channel "carer", sent true/false).
"""

import logging
import time
from typing import Any

import httpx

from backend import settings
from backend import spacetime_client as st

log = logging.getLogger("nemo.alerts")


def notify(type: str, message: str) -> tuple[bool, str]:
    """POST the alert to the notifier. Returns (ok, error). Never raises."""
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

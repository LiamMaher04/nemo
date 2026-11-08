"""Alerts: text the carer through the notifier (Photon), or say something on Nemo's speaker.

notify(type, message) only calls the notifier. send_carer_alert(type, message) calls it AND writes
the alert to Spacetime's alerts table (channel "carer", sent true/false).

sender_loop() runs with the FastAPI app. Spacetime decides WHEN to alert (check_alerts,
report_possible_fall, request_carer_alert all write unsent rows to alerts); this loop delivers them
and marks them sent:
- channel "carer": texted to CARER_PHONE, only while CARER_ALERTS is on;
- channel "spoken": turned into speech and played on Nemo (POST {NEMO_URL}/play), always, whatever
  CARER_ALERTS says.
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
_spoken_wav: dict[int, bytes] = {}  # alert id -> its speech, so a retry doesn't make it again


def play_on_nemo(wav: bytes) -> tuple[bool, str]:
    """POST a WAV to Nemo's /play (multipart "file", as talk_bridge does). Returns (ok, error)."""
    if not settings.NEMO_URL:
        return False, "NEMO_URL is empty"
    try:
        r = httpx.post(f"{settings.NEMO_URL}/play", files={"file": ("alert.wav", wav, "audio/wav")},
                       timeout=httpx.Timeout(60.0, connect=5.0))  # /play answers when playback ends
    except Exception as exc:
        return False, f"Nemo unreachable: {type(exc).__name__}"
    return (True, "") if r.status_code == 200 else (False, f"Nemo /play HTTP {r.status_code}")


def _speak(alert_id: int, message: str) -> tuple[bool, str]:
    from backend import speech
    wav = _spoken_wav.get(alert_id)
    if wav is None:
        try:
            wav, voice = speech.speak(message)
        except Exception as exc:
            return False, f"speech failed: {exc}"
        _spoken_wav[alert_id] = wav
        log.info("alert #%d: speech ready (%s voice, %d bytes)", alert_id, voice, len(wav))
    return play_on_nemo(wav)


def send_pending_once() -> int:
    """Deliver every unsent alert once: carer texts (if CARER_ALERTS is on) and spoken alerts.
    Returns how many were delivered."""
    sent = 0
    for a in st.sql("SELECT * FROM alerts WHERE sent = false"):
        alert_id, channel = int(a["id"]), a["channel"]
        if channel == "carer" and not settings.CARER_ALERTS:
            continue  # stays unsent; turning CARER_ALERTS on later sends it
        if channel not in ("carer", "spoken"):
            continue
        if _tries.get(alert_id, 0) >= MAX_TRIES:
            continue  # gave up; it stays unsent so nothing new of that type is raised until it's cleared
        ok, error = notify(a["type"], a["message"]) if channel == "carer" else _speak(alert_id, a["message"])
        if ok:
            st.call("mark_alert_sent", alert_id, True)
            _tries.pop(alert_id, None)
            _spoken_wav.pop(alert_id, None)
            sent += 1
            log.info("alert #%d %s %s", alert_id, a["type"],
                     "texted to the carer" if channel == "carer" else "spoken on Nemo")
        else:
            _tries[alert_id] = _tries.get(alert_id, 0) + 1
            left = MAX_TRIES - _tries[alert_id]
            log.warning("alert #%d %s (%s) not delivered (%s); %s", alert_id, a["type"], channel, error,
                        f"{left} tries left" if left else "giving up")
            if not left:
                _spoken_wav.pop(alert_id, None)
    return sent


async def sender_loop() -> None:
    """Every SEND_EVERY_S seconds, deliver any unsent alerts. Runs until cancelled.

    Spoken alerts are always delivered. Carer alerts only while CARER_ALERTS is on: with it off they
    stay unsent (reset_memory clears them), so turning it back on can send any still waiting.
    """
    log.info("alert sender running every %d s (spoken alerts on Nemo: yes; carer texts: %s)",
             SEND_EVERY_S, "yes" if settings.CARER_ALERTS else "no, CARER_ALERTS is off")
    while True:
        try:
            await asyncio.to_thread(send_pending_once)
        except Exception as exc:  # Spacetime unreachable etc: try again next round
            log.warning("alert sender round failed: %s", exc)
        await asyncio.sleep(SEND_EVERY_S)

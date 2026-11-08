"""Possible-fall check, from the camera alone (Nemo has no motion sensor).

Every frame Nemo returns (kept or dropped by vision) goes through observe(). If for FALL_WINDOW_S
in a row the frames are very dark (camera face down or covered), or a still view with very little
detail (a floor or ceiling seen from the ground), the newest frame goes to Super VL once, in the
vl.py worker. If Super VL says yes, Spacetime's report_possible_fall raises the carer alert.

Frames must keep arriving: a gap longer than MAX_GAP_S (Nemo off or out of range) starts again,
so a switched-off device never looks like a fall. Any normal frame ends the streak.

Thresholds are from 303 normal frames of the hotel room (dim): brightness never below 45 and
detail (grey spread) never below 25, so these sit well under anything normal.
"""

import logging
import threading
import time
from typing import Any

import cv2
import numpy as np

from backend import settings

log = logging.getLogger("nemo.fall")

DARK_MEAN = 25.0  # mean grey level (0-255) below this = very dark
LOW_DETAIL_STD = 12.0  # grey spread below this = very little detail ...
STILL_DIFF = 3.0  # ... AND the view barely changed since the last frame (mean diff of 64x48 thumbnails)
MAX_GAP_S = 10.0  # frames further apart than this: start again

_lock = threading.Lock()
_since: float | None = None  # when the current streak of dark / featureless frames began
_last_ts: float | None = None
_last_thumb: np.ndarray | None = None
_asked = False  # Super VL already asked for this streak
stats: dict[str, Any] = {"observed": 0, "suspicious": 0, "asked": 0}


def measure(jpeg: bytes) -> dict[str, Any] | None:
    """Brightness, detail and a small thumbnail of a JPEG (decoded at 1/4 size, a few ms)."""
    grey = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_REDUCED_GRAYSCALE_4)
    if grey is None:
        return None
    thumb = cv2.resize(grey, (64, 48), interpolation=cv2.INTER_AREA).astype(np.int16)
    return {"mean": float(grey.mean()), "std": float(grey.std()), "thumb": thumb}


def observe(jpeg: bytes, now_s: float | None = None) -> str:
    """Look at one frame. Returns "off", "unreadable", "normal", "suspicious" or "asked".

    now_s is for the demo (a fake clock); the frame loop leaves it as now.
    """
    global _since, _last_ts, _last_thumb, _asked
    if not settings.FALL_CHECK:
        return "off"
    now = time.time() if now_s is None else now_s
    m = measure(jpeg)
    if m is None:
        return "unreadable"
    with _lock:
        stats["observed"] += 1
        gap = (now - _last_ts) if _last_ts is not None else 0.0
        still = _last_thumb is not None and float(np.abs(m["thumb"] - _last_thumb).mean()) < STILL_DIFF
        _last_ts, _last_thumb = now, m["thumb"]
        dark = m["mean"] < DARK_MEAN
        flat = m["std"] < LOW_DETAIL_STD and still
        if not (dark or flat):
            _since, _asked = None, False
            return "normal"
        stats["suspicious"] += 1
        if _since is None or gap > MAX_GAP_S:
            _since, _asked = now, False
        seconds = now - _since
        if _asked or seconds < settings.FALL_WINDOW_S:
            return "suspicious"
        _asked = True
        stats["asked"] += 1

    if not settings.SUPER_VL:
        log.warning("possible fall: %.0f s of %s frames, but SUPER_VL is off so it can't be confirmed",
                    seconds, "dark" if dark else "still, featureless")
        return "asked"
    from backend import vl
    queued = vl.submit("fall", vl.fall_check_job, jpeg, now * 1000)
    if not queued:  # the worker's queue was full: try again on the next frame
        with _lock:
            _asked = False
    log.info("possible fall: %.0f s of %s frames (brightness %.0f, detail %.0f); asking Super VL%s",
             seconds, "dark" if dark else "still, featureless", m["mean"], m["std"],
             "" if queued else " (not queued: worker busy)")
    return "asked"

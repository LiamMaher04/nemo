"""Frame gating: drop blurry frames and near-duplicates of the last kept frame."""

import cv2
import numpy as np

from backend.vision import settings

THUMB_SIZE = (64, 48)  # width, height of the greyscale thumbnail used for the duplicate check

# State: the last kept frame's thumbnail and timestamp.
_last_thumb: np.ndarray | None = None
_last_kept_ts_ms: float | None = None


def sharpness(grey: np.ndarray) -> float:
    """Variance of the Laplacian on the full-resolution greyscale frame (Spacetime's scale)."""
    return float(cv2.Laplacian(grey, cv2.CV_64F).var())


def check(grey: np.ndarray, sharp: float, ts_ms: float) -> str:
    """Return "" to keep the frame, otherwise the reason it is dropped.

    Keeping a frame makes it the new reference for the duplicate check.
    """
    global _last_thumb, _last_kept_ts_ms

    if sharp < settings.SHARPNESS_GATE:
        return f"blurry ({sharp:.1f} < {settings.SHARPNESS_GATE:g})"

    thumb = cv2.resize(grey, THUMB_SIZE, interpolation=cv2.INTER_AREA).astype(np.int16)
    if _last_thumb is not None and _last_kept_ts_ms is not None:
        diff = float(np.abs(thumb - _last_thumb).mean())
        since_s = (ts_ms - _last_kept_ts_ms) / 1000.0
        if diff < settings.DUPLICATE_DIFF_MAX and since_s < settings.KEEPALIVE_S:
            return f"duplicate (diff {diff:.2f} < {settings.DUPLICATE_DIFF_MAX:g}, {since_s:.1f}s since kept)"

    _last_thumb = thumb
    _last_kept_ts_ms = ts_ms
    return ""

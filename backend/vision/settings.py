"""Vision settings, read from the .env file at the repo root (same way as backend/settings.py)."""

import os
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
load_dotenv(REPO_ROOT / ".env")


def _clean(value: str | None, default: str) -> str:
    """Strip inline '# comments' and whitespace that .env lines may carry."""
    if value is None:
        return default
    value = value.split("#", 1)[0].strip()
    return value or default


DETECTOR_WEIGHTS: str = _clean(os.getenv("DETECTOR_WEIGHTS"), "yoloe-26s-seg.pt")
DETECT_CONF: float = float(_clean(os.getenv("DETECT_CONF"), "0.25"))
DETECT_IMGSZ: int = int(_clean(os.getenv("DETECT_IMGSZ"), "960"))

# Variance of the Laplacian on the full-resolution greyscale frame. Below this the frame is
# dropped. Spacetime's FRAME_SHARP_MIN (100) is a separate, higher bar for "clearly in view".
SHARPNESS_GATE: float = float(_clean(os.getenv("SHARPNESS_GATE"), "40"))
# Mean absolute difference (0 to 255) between 64x48 greyscale thumbnails of this frame and the
# last kept frame. Below this the frame is a near-duplicate.
DUPLICATE_DIFF_MAX: float = float(_clean(os.getenv("DUPLICATE_DIFF_MAX"), "2.0"))
# If nothing has been kept for this many seconds, keep the next sharp duplicate anyway.
KEEPALIVE_S: float = float(_clean(os.getenv("KEEPALIVE_S"), "3"))


def weights_path() -> Path:
    """Find DETECTOR_WEIGHTS: as given, then in backend/, then at the repo root.

    If none exists, the bare name is returned and ultralytics downloads it.
    """
    given = Path(DETECTOR_WEIGHTS).expanduser()
    if given.is_absolute():
        return given
    for folder in (BACKEND_DIR, REPO_ROOT):
        if (folder / given).exists():
            return folder / given
    return given

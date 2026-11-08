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


# DINOv2 (area and item matching). Revision pinned so the weights never change under us.
DINO_MODEL: str = _clean(os.getenv("DINO_MODEL"), "facebook/dinov2-small")
DINO_REVISION: str = _clean(os.getenv("DINO_REVISION"), "ed25f3a31f01632728cabb09d1542f84ab7b0056")
# Reference photos: <REFS_DIR>/areas/<area_id>/*.jpg and <REFS_DIR>/items/<item_id>/*.jpg
REFS_DIR: Path = REPO_ROOT / _clean(os.getenv("REFS_DIR"), "backend/vision/refs")

# Area voting: kept frames from the last AREA_VOTE_S seconds each vote for one area (or none).
AREA_VOTE_S: float = float(_clean(os.getenv("AREA_VOTE_S"), "3"))
# A frame votes only if its best area scores at least this (cosine similarity) ...
AREA_SIM_MIN: float = float(_clean(os.getenv("AREA_SIM_MIN"), "0.55"))
# ... and beats the second-best area by at least this.
AREA_MARGIN_MIN: float = float(_clean(os.getenv("AREA_MARGIN_MIN"), "0.03"))
# The winning area needs at least this share of the window's votes, else area_id is "".
AREA_VOTE_MIN: float = float(_clean(os.getenv("AREA_VOTE_MIN"), "0.5"))

# Item matching: below either of these the sighting is ambiguous (item_id "").
ITEM_SIM_MIN: float = float(_clean(os.getenv("ITEM_SIM_MIN"), "0.40"))
ITEM_MARGIN_MIN: float = float(_clean(os.getenv("ITEM_MARGIN_MIN"), "0.05"))


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

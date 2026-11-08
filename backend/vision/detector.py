"""YOLOE with text prompts. Loaded and given its classes once, on first use."""

import contextlib
import logging
import time
from dataclasses import dataclass

import numpy as np
import torch
from ultralytics import YOLOE

from backend.vision import classes, settings

log = logging.getLogger(__name__)


@dataclass
class Box:
    kind: str  # "item" or "furniture"
    name: str  # item_id, or the fixed furniture name
    wording: str  # the YOLOE class that fired
    conf: float
    xyxy: tuple[float, float, float, float]  # full-frame pixels


_model: YOLOE | None = None
_device: str = "cpu"
# YOLOE class index -> (kind, name, wording)
_class_map: list[tuple[str, str, str]] = []


def pick_device() -> str:
    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def _build_class_map() -> list[tuple[str, str, str]]:
    out: list[tuple[str, str, str]] = []
    for item_id, wordings in classes.ITEMS.items():
        out += [("item", item_id, w) for w in wordings]
    for name, wordings in classes.FURNITURE.items():
        out += [("furniture", name, w) for w in wordings]
    words = [w for _, _, w in out]
    dupes = {w for w in words if words.count(w) > 1}
    if dupes:
        raise ValueError(f"Wordings must be unique in classes.py: {sorted(dupes)}")
    return out


def load() -> float:
    """Load the model and set its text-prompt classes. Returns seconds taken (0 if already loaded)."""
    global _model, _device, _class_map
    if _model is not None:
        return 0.0
    start = time.perf_counter()
    weights = settings.weights_path()
    _class_map = _build_class_map()
    _device = pick_device()
    # Ultralytics looks for (and downloads) the text encoder, e.g. mobileclip2_b.ts, in the
    # current folder. Work from the weights' folder (backend/ if the weights must be
    # downloaded) so both files live together.
    found = weights.exists()
    folder = weights.resolve().parent if found else settings.BACKEND_DIR
    with contextlib.chdir(folder):
        model = YOLOE(str(weights.resolve()) if found else weights.name)
        model.set_classes([w for _, _, w in _class_map])
    _model = model
    seconds = time.perf_counter() - start
    log.info("YOLOE %s loaded on %s with %d wordings in %.1fs", weights.name, _device, len(_class_map), seconds)
    return seconds


def detect(bgr: np.ndarray) -> list[Box]:
    """Run YOLOE on a full-resolution BGR frame and return every box above DETECT_CONF."""
    load()
    assert _model is not None
    result = _model.predict(
        bgr,
        conf=settings.DETECT_CONF,
        imgsz=settings.DETECT_IMGSZ,
        agnostic_nms=False,
        device=_device,
        verbose=False,
    )[0]
    boxes: list[Box] = []
    if result.boxes is None:
        return boxes
    xyxy = result.boxes.xyxy.cpu().numpy()
    confs = result.boxes.conf.cpu().numpy()
    cls = result.boxes.cls.cpu().numpy().astype(int)
    for (x1, y1, x2, y2), conf, c in zip(xyxy, confs, cls):
        kind, name, wording = _class_map[c]
        boxes.append(Box(kind, name, wording, float(conf), (float(x1), float(y1), float(x2), float(y2))))
    return boxes

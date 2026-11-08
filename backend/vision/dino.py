"""DINOv2 fingerprints: one unit-length vector per image, compared by cosine similarity."""

import logging
import time
from pathlib import Path

import cv2
import numpy as np
import torch
from transformers import AutoModel

from backend.vision import settings
from backend.vision.detector import pick_device

log = logging.getLogger(__name__)

SIZE = 224  # DINOv2 input size (a multiple of its 14 px patches)
_MEAN = np.array([0.485, 0.456, 0.406], np.float32)  # ImageNet, as DINOv2 was trained
_STD = np.array([0.229, 0.224, 0.225], np.float32)

_model: torch.nn.Module | None = None
_device = "cpu"


def load() -> float:
    """Load the model once. Returns seconds taken (0 if already loaded)."""
    global _model, _device
    if _model is not None:
        return 0.0
    start = time.perf_counter()
    _device = pick_device()
    _model = AutoModel.from_pretrained(settings.DINO_MODEL, revision=settings.DINO_REVISION).eval().to(_device)
    seconds = time.perf_counter() - start
    log.info("DINOv2 %s loaded on %s in %.1fs", settings.DINO_MODEL, _device, seconds)
    return seconds


def square(bgr: np.ndarray) -> np.ndarray:
    """Pad to a square with grey so an item crop keeps its shape."""
    h, w = bgr.shape[:2]
    side = max(h, w)
    out = np.full((side, side, 3), 124, np.uint8)
    out[(side - h) // 2 : (side - h) // 2 + h, (side - w) // 2 : (side - w) // 2 + w] = bgr
    return out


def embed(images_bgr: list[np.ndarray]) -> np.ndarray:
    """Fingerprint a batch of BGR images (each squashed to 224 x 224). Returns (n, 384), unit length."""
    load()
    assert _model is not None
    if not images_bgr:
        return np.zeros((0, 384), np.float32)
    batch = np.stack([
        (cv2.cvtColor(cv2.resize(img, (SIZE, SIZE), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2RGB)
         .astype(np.float32) / 255.0 - _MEAN) / _STD
        for img in images_bgr
    ])
    x = torch.from_numpy(batch).permute(0, 3, 1, 2).to(_device)
    with torch.inference_mode():
        feats = _model(pixel_values=x).pooler_output  # the CLS token after the final layer norm
        feats = torch.nn.functional.normalize(feats, dim=1)
    return feats.cpu().numpy()


def embed_files(paths: list[Path], as_crop: bool, batch: int = 16) -> np.ndarray:
    """Fingerprint image files, in batches. Unreadable files are skipped with a warning."""
    images: list[np.ndarray] = []
    for path in paths:
        img = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if img is None:
            print(f"  warning: could not read {path}")
            continue
        images.append(square(img) if as_crop else img)
    parts = [embed(images[i : i + batch]) for i in range(0, len(images), batch)]
    return np.concatenate(parts) if parts else np.zeros((0, 384), np.float32)


def image_files(folder: Path) -> list[Path]:
    return sorted(p for p in folder.iterdir() if p.suffix.lower() in (".jpg", ".jpeg", ".png"))

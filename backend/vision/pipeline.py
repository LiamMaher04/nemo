"""process(): one JPEG in, the add_sighting and add_frame reports out (or why it was dropped)."""

import base64
import json
import os
import time
from dataclasses import dataclass, field

import cv2
import numpy as np

from backend.vision import areas, classes, detector, dino, gate, item_match
from backend.vision.areas import AreaMatch
from backend.vision.detector import Box

THUMB_WIDTH = 160
THUMB_PAD = 0.2  # padding around the item box, as a fraction of its width and height
THUMB_JPEG_QUALITY = 80
FACE_SEARCH_WIDTH = 640  # the face cascade runs on a copy this wide
FACE_GROW = 0.2  # widen each face box by this fraction on every side before blurring
ITEM_CROP_PAD = 0.1  # padding around the item box for its DINOv2 crop

_loaded = False

# Importing ultralytics turns OpenCV threading off, which makes the face cascade about 4x
# slower. Turn it back on (we don't use PyTorch DataLoaders, the reason ultralytics does it).
cv2.setNumThreads(os.cpu_count() or 1)

_face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")


@dataclass
class VisionResult:
    kept: bool
    drop_reason: str  # "" if kept
    sharpness: float  # filled for every frame, kept or dropped
    sightings: list[dict] = field(default_factory=list)  # add_sighting order, 14 keys
    frame: dict | None = None  # add_frame order, 7 keys; None if dropped
    furniture_boxes: list[tuple[str, list[int], float]] = field(default_factory=list)  # for drawing
    ms: float = 0.0  # time spent in process()
    area: AreaMatch | None = None  # this frame's area vote and scores, for printing
    yoloe_ms: float = 0.0
    dino_ms: float = 0.0


def _dumps(value: object) -> str:
    return json.dumps(value, separators=(",", ":"))


def _iou(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def _merge_same(boxes: list[Box]) -> list[Box]:
    """Several wordings of the same thing on overlapping boxes: keep only the best."""
    kept: list[Box] = []
    for box in sorted(boxes, key=lambda b: b.conf, reverse=True):
        if not any(k.name == box.name and _iou(k.xyxy, box.xyxy) > classes.SAME_THING_IOU for k in kept):
            kept.append(box)
    return kept


def _group_items(items: list[Box]) -> list[list[Box]]:
    """Group boxes of different items that overlap (IoU over AMBIGUOUS_IOU). Best first in each group."""
    parent = list(range(len(items)))

    def root(i: int) -> int:
        while parent[i] != i:
            i = parent[i]
        return i

    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            if items[i].name != items[j].name and _iou(items[i].xyxy, items[j].xyxy) > classes.AMBIGUOUS_IOU:
                parent[root(j)] = root(i)
    groups: dict[int, list[Box]] = {}
    for i, box in enumerate(items):
        groups.setdefault(root(i), []).append(box)
    return [sorted(g, key=lambda b: b.conf, reverse=True) for g in groups.values()]


def _match_furniture(item: Box, furniture: list[Box], frame_w: int) -> tuple[str, str]:
    """Return (furniture name, rel_pos_json) for the furniture the item is on or near."""
    cx = (item.xyxy[0] + item.xyxy[2]) / 2
    cy = (item.xyxy[1] + item.xyxy[3]) / 2

    def area(f: Box) -> float:
        return (f.xyxy[2] - f.xyxy[0]) * (f.xyxy[3] - f.xyxy[1])

    inside = [f for f in furniture if f.xyxy[0] <= cx <= f.xyxy[2] and f.xyxy[1] <= cy <= f.xyxy[3]]
    best: Box | None = min(inside, key=area) if inside else None  # smallest = most specific
    if best is None:
        def gap(f: Box) -> float:
            dx = max(f.xyxy[0] - cx, 0.0, cx - f.xyxy[2])
            dy = max(f.xyxy[1] - cy, 0.0, cy - f.xyxy[3])
            return float(np.hypot(dx, dy))

        near = [f for f in furniture if gap(f) <= classes.NEAR_FURNITURE_FRAC * frame_w]
        best = min(near, key=gap) if near else None
    if best is None:
        return "", "[]"
    x1, y1, x2, y2 = best.xyxy
    rx = min(max((cx - x1) / max(x2 - x1, 1.0), 0.0), 1.0)
    ry = min(max((cy - y1) / max(y2 - y1, 1.0), 0.0), 1.0)
    return best.name, _dumps([round(rx, 3), round(ry, 3)])


def blur_faces(bgr: np.ndarray, grey: np.ndarray) -> np.ndarray:
    """Copy of the frame with every face the Haar cascade finds blurred out.

    All face blurring goes through this one function (thumbnails and --save), so the face
    detector can be swapped (YuNet is next) without touching anything else.

    The cascade runs on a copy at most FACE_SEARCH_WIDTH wide (much faster), and each face box
    is widened by FACE_GROW, because Haar boxes leave the chin and hairline showing.
    """
    out = bgr.copy()
    h_img, w_img = grey.shape[:2]
    scale = min(1.0, FACE_SEARCH_WIDTH / w_img)
    small = cv2.resize(grey, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA) if scale < 1 else grey
    faces = _face_cascade.detectMultiScale(small, scaleFactor=1.1, minNeighbors=5, minSize=(20, 20))
    for fx, fy, fw, fh in faces:
        x, y, w, h = fx / scale, fy / scale, fw / scale, fh / scale
        gx, gy = w * FACE_GROW, h * FACE_GROW
        x1, y1 = max(int(x - gx), 0), max(int(y - gy), 0)
        x2, y2 = min(int(x + w + gx), w_img), min(int(y + h + gy), h_img)
        out[y1:y2, x1:x2] = cv2.GaussianBlur(out[y1:y2, x1:x2], (0, 0), sigmaX=max(w, h) / 6)
    return out


def _thumb_b64(blurred: np.ndarray, xyxy: tuple[float, float, float, float]) -> str:
    h, w = blurred.shape[:2]
    x1, y1, x2, y2 = xyxy
    px, py = (x2 - x1) * THUMB_PAD, (y2 - y1) * THUMB_PAD
    crop = blurred[max(int(y1 - py), 0) : min(int(y2 + py), h), max(int(x1 - px), 0) : min(int(x2 + px), w)]
    if crop.size == 0:
        return ""
    scale = THUMB_WIDTH / crop.shape[1]
    crop = cv2.resize(crop, (THUMB_WIDTH, max(int(crop.shape[0] * scale), 1)), interpolation=cv2.INTER_AREA)
    ok, jpg = cv2.imencode(".jpg", crop, [cv2.IMWRITE_JPEG_QUALITY, THUMB_JPEG_QUALITY])
    return base64.b64encode(jpg.tobytes()).decode("ascii") if ok else ""


def _xywh(xyxy: tuple[float, float, float, float]) -> list[int]:
    x1, y1, x2, y2 = xyxy
    return [round(x1), round(y1), round(x2 - x1), round(y2 - y1)]


def load() -> None:
    """Load YOLOE, and DINOv2 plus its reference fingerprints. Once; process() calls it too."""
    global _loaded
    if _loaded:
        return
    t = time.perf_counter()
    detector.load()
    print(f"YOLOE ready in {time.perf_counter() - t:.1f}s", flush=True)
    t = time.perf_counter()
    dino.load()
    areas.load_refs()
    item_match.load_refs()
    print(f"DINOv2 and references ready in {time.perf_counter() - t:.1f}s", flush=True)
    _loaded = True


def _crop(bgr: np.ndarray, xyxy: tuple[float, float, float, float], pad: float) -> np.ndarray:
    h, w = bgr.shape[:2]
    x1, y1, x2, y2 = xyxy
    px, py = (x2 - x1) * pad, (y2 - y1) * pad
    return bgr[max(int(y1 - py), 0) : min(int(y2 + py), h), max(int(x1 - px), 0) : min(int(x2 + px), w)]


def _identify(group: list[Box], crop_fp: np.ndarray | None) -> tuple[str, list[list], float]:
    """(item_id, candidates, match_margin) for one object (a group of overlapping item boxes)."""
    if crop_fp is not None:  # DINOv2 decides
        ranked = item_match.rank(crop_fp)
        item_id, margin = item_match.decide(ranked)
        return item_id, [[i, round(sim, 4)] for i, sim in ranked[:3]], margin
    candidates = [[b.name, round(b.conf, 4)] for b in group]
    if len(group) == 1:
        return group[0].name, candidates, 1.0  # no references: the YOLOE wording decides
    return "", candidates, group[0].conf - group[1].conf  # different items, same box


def process(jpeg_bytes: bytes, frame_id: int, ts_ms: float) -> VisionResult:
    """Gate one frame, run YOLOE and DINOv2 on it if kept, and build the add_sighting and add_frame reports."""
    load()
    start = time.perf_counter()

    def done(result: VisionResult) -> VisionResult:
        result.ms = (time.perf_counter() - start) * 1000
        return result

    bgr = cv2.imdecode(np.frombuffer(jpeg_bytes, np.uint8), cv2.IMREAD_COLOR)
    if bgr is None:
        return done(VisionResult(False, "could not decode JPEG", 0.0))
    grey = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    sharp = gate.sharpness(grey)
    reason = gate.check(grey, sharp, ts_ms)
    if reason:
        return done(VisionResult(False, reason, sharp))

    t = time.perf_counter()
    boxes = detector.detect(bgr)
    yoloe_ms = (time.perf_counter() - t) * 1000
    items = _merge_same([b for b in boxes if b.kind == "item"])
    furniture = _merge_same([b for b in boxes if b.kind == "furniture"])
    groups = _group_items(items)

    # One DINOv2 batch: the whole frame (if there are area references), then one crop per
    # object whose YOLOE item(s) all have reference crops.
    t = time.perf_counter()
    use_dino = [all(item_match.has_refs(b.name) for b in g) for g in groups]
    images = [bgr] if areas.has_refs() else []
    images += [dino.square(_crop(bgr, g[0].xyxy, ITEM_CROP_PAD)) for g, use in zip(groups, use_dino) if use]
    fps = dino.embed(images) if images else np.zeros((0, 384), np.float32)
    frame_fp = fps[0] if areas.has_refs() else None
    crop_fps = iter(fps[1:] if areas.has_refs() else fps)
    area = areas.match(frame_fp, ts_ms)
    dino_ms = (time.perf_counter() - t) * 1000 if images else 0.0

    frame_w = bgr.shape[1]
    blurred = blur_faces(bgr, grey) if items else bgr
    sharp_r = round(sharp, 2)

    sightings: list[dict] = []
    items_seen: set[str] = set()
    for group, use in zip(groups, use_dino):
        top = group[0]
        item_id, candidates, margin = _identify(group, next(crop_fps) if use else None)
        if item_id:
            items_seen.add(item_id)
        furn, rel_pos = _match_furniture(top, furniture, frame_w)
        sightings.append({
            "ts_ms": ts_ms,
            "frame_id": frame_id,
            "area_id": area.area_id,
            "area_conf": area.area_conf,
            "label": top.wording,
            "det_conf": round(top.conf, 4),
            "item_id": item_id,
            "candidates_json": _dumps(candidates),
            "match_margin": round(margin, 4),
            "furniture": furn,
            "rel_pos_json": rel_pos,
            "sharpness": sharp_r,
            "bbox_json": _dumps(_xywh(top.xyxy)),
            "thumb_b64": _thumb_b64(blurred, top.xyxy),
        })

    frame = {
        "ts_ms": ts_ms,
        "frame_id": frame_id,
        "area_id": area.area_id,
        "area_conf": area.area_conf,
        "furniture_in_view_json": _dumps(sorted({f.name for f in furniture})),
        "items_seen_json": _dumps(sorted(items_seen)),
        "sharpness": sharp_r,
    }
    furniture_boxes = [(f.name, _xywh(f.xyxy), round(f.conf, 4)) for f in furniture]
    return done(VisionResult(True, "", sharp, sightings, frame, furniture_boxes, area=area,
                             yoloe_ms=yoloe_ms, dino_ms=dino_ms))

"""Vision pipeline (Josie's area). One function the backend calls per frame.

process(jpeg_bytes, frame_id, ts_ms) -> list of sighting dicts, each with the add_sighting fields
from docs/interfaces.md (item_id, label, det_conf, bbox, in_hand, room_id, ...).

Stages to fill in: gating (blur/duplicates) -> detector (YOLOE / YOLO-World) -> tracker ->
DINOv2 instance match -> room (QR/AprilTag first) -> anchor + relation -> thumbnail (faces blurred).

Until the detector exists this returns nothing, so /frame just saves frames and logs fps.
"""
from __future__ import annotations

from typing import Any


def process(jpeg: bytes, frame_id: int, ts_ms: float) -> list[dict[str, Any]]:
    return []

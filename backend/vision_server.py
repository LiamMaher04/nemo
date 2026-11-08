"""Vision on its own, for a GPU box (Brev): JPEG in, Josie's VisionResult out as JSON.

Runs the same backend.vision.process() the laptop runs (gates, face blur, YOLOE, DINOv2), with
the same settings from the repo-root .env (SHARPNESS_GATE, DETECT_*, REFS_DIR, ...). Needs no API
keys and talks to nothing else. The laptop's frame loop calls it when VISION_URL is set.

Run from the repo root:
    uvicorn backend.vision_server:app --host 127.0.0.1 --port 8001

127.0.0.1 only: the laptop reaches it through `brev port-forward`, never over the open internet.
"""

import dataclasses
import logging
import threading
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.concurrency import run_in_threadpool

from backend.vision import areas, detector, dino, item_match, pipeline
from backend.vision import settings as vs

log = logging.getLogger("nemo.vision_server")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# One frame at a time: the models and the gate's duplicate check keep state between frames.
_lock = threading.Lock()
_load_error: str | None = "loading"
_load_s: float | None = None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Load YOLOE, DINOv2 and the reference fingerprints once (on CUDA if there is one)."""
    global _load_error, _load_s
    started = time.perf_counter()
    try:
        await run_in_threadpool(pipeline.load)
        _load_error = None
        _load_s = round(time.perf_counter() - started, 1)
        log.info("vision ready on %s in %.1f s (REFS_DIR %s)", detector._device, _load_s, vs.REFS_DIR)
    except Exception as exc:  # /health says why; /process answers 503
        _load_error = str(exc)
        log.exception("vision failed to load")
    yield


app = FastAPI(title="Nemo vision server", lifespan=lifespan)


@app.get("/health")
def health() -> dict:
    import torch

    return {
        "ok": _load_error is None,
        "loaded": _load_error is None,
        "error": _load_error,
        "load_s": _load_s,
        "device": detector._device,
        "dino_device": dino._device,
        "cuda": torch.cuda.is_available(),
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "refs_dir": str(vs.REFS_DIR),
        "area_refs": {k: len(v) for k, v in areas._refs.items()},
        "item_refs": {k: len(v) for k, v in item_match._refs.items()},
        # So you can check they match the laptop's .env: different gates mean different results.
        "settings": {
            "SHARPNESS_GATE": vs.SHARPNESS_GATE,
            "DETECT_CONF": vs.DETECT_CONF,
            "DETECT_IMGSZ": vs.DETECT_IMGSZ,
            "DETECTOR_WEIGHTS": vs.DETECTOR_WEIGHTS,
            "DINO_MODEL": vs.DINO_MODEL,
        },
    }


def _run(jpeg: bytes, frame_id: int, ts_ms: float) -> dict:
    with _lock:
        result = pipeline.process(jpeg, frame_id, ts_ms)
    return {
        "kept": result.kept,
        "drop_reason": result.drop_reason,
        "sharpness": result.sharpness,
        "sightings": result.sightings,
        "frame": result.frame,
        "furniture_boxes": [list(t) for t in result.furniture_boxes],
        "matched_by": result.matched_by,
        "ms": result.ms,
        "yoloe_ms": result.yoloe_ms,
        "dino_ms": result.dino_ms,
        "area": dataclasses.asdict(result.area) if result.area is not None else None,
    }


@app.post("/process")
async def process(request: Request) -> dict:
    """Body: raw JPEG. Headers: X-Frame-Id (int), X-Frame-Ts (UTC ms). Returns the VisionResult."""
    started = time.perf_counter()
    if _load_error is not None:
        raise HTTPException(status_code=503, detail=f"vision not ready: {_load_error}")
    body = await request.body()
    if not body.startswith(b"\xff\xd8"):
        raise HTTPException(status_code=400, detail="Body is not a JPEG")
    try:
        frame_id = int(request.headers["X-Frame-Id"])
        ts_ms = float(request.headers["X-Frame-Ts"])
    except (KeyError, ValueError):
        raise HTTPException(status_code=400, detail="X-Frame-Id and X-Frame-Ts headers are required")

    out = await run_in_threadpool(_run, body, frame_id, ts_ms)
    out["server_ms"] = (time.perf_counter() - started) * 1000  # the whole request, as the server saw it
    log.info("frame %d %s: process %.0f ms (YOLOE %.0f, DINOv2 %.0f), request %.0f ms, %d sightings",
             frame_id, "kept" if out["kept"] else "dropped (" + out["drop_reason"] + ")",
             out["ms"], out["yoloe_ms"], out["dino_ms"], out["server_ms"], len(out["sightings"]))
    return out

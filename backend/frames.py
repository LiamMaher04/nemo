"""The frame loop: one JPEG in -> Josie's vision -> add_sighting / add_frame in Spacetime.

Frames arrive by POST /frame (FRAME_SOURCE=post) or by fetching NEMO_JPG_URL once a second
(FRAME_SOURCE=pull). Both call handle(). Only one frame is processed at a time: a frame that
arrives while another is still being processed is skipped, not queued.

backend.vision (and so torch/ultralytics) is imported lazily, so scripts that import backend.main
without running the app stay quick.
"""

import asyncio
import logging
import threading
import time
from collections import deque
from typing import Any

import httpx

from backend import settings
from backend import spacetime_client as st

log = logging.getLogger("nemo.frames")

_busy = threading.Lock()
# Set while /ask is answering: new frames are skipped so speech to text gets the whole CPU.
answering = threading.Event()
_vision_ms: deque[float] = deque(maxlen=20)  # process() time of the last 20 processed frames
history: deque[dict] = deque(maxlen=200)  # per processed frame: frame_id, kept, vision_ms, spacetime_ms
_next_frame_id = 0
stats = {"processed": 0, "kept": 0, "dropped": 0, "skipped_busy": 0, "spacetime_errors": 0}


def _first_frame_id() -> int:
    """Carry on numbering after the newest saved frame, so ids stay unique across restarts."""
    ids = [int(p.stem) for p in settings.FRAMES_DIR.glob("*.jpg") if p.stem.isdigit()]
    return max(ids, default=0) + 1


def _save_frame(frame_id: int, jpeg: bytes) -> None:
    """Keep the last FRAMES_KEPT kept frames as captures/frames/<frame_id>.jpg."""
    settings.FRAMES_DIR.mkdir(parents=True, exist_ok=True)
    (settings.FRAMES_DIR / f"{frame_id}.jpg").write_bytes(jpeg)
    saved = sorted((p for p in settings.FRAMES_DIR.glob("*.jpg") if p.stem.isdigit()), key=lambda p: int(p.stem))
    for old in saved[: max(0, len(saved) - settings.FRAMES_KEPT)]:
        old.unlink(missing_ok=True)


def avg_vision_ms() -> float | None:
    return round(sum(_vision_ms) / len(_vision_ms), 1) if _vision_ms else None


def warm_up() -> None:
    """Load YOLOE once at startup, holding the busy lock so frames during loading are skipped."""
    global _next_frame_id
    with _busy:
        started = time.perf_counter()
        from backend.vision import detector
        detector.load()
        _next_frame_id = _first_frame_id()
        log.info("vision ready in %.1f s (next frame_id %d)", time.perf_counter() - started, _next_frame_id)


def handle(jpeg: bytes) -> dict[str, Any]:
    """Process one frame if nothing else is being processed. Never raises."""
    global _next_frame_id
    if answering.is_set():
        stats["skipped_busy"] += 1
        return {"skipped": "answering"}
    if not _busy.acquire(blocking=False):
        stats["skipped_busy"] += 1
        return {"skipped": "busy"}
    try:
        from backend.vision import process

        started = time.perf_counter()
        if _next_frame_id == 0:
            _next_frame_id = _first_frame_id()
        frame_id = _next_frame_id
        _next_frame_id += 1
        ts_ms = time.time() * 1000

        result = process(jpeg, frame_id, ts_ms)
        vision_ms = result.ms
        _vision_ms.append(vision_ms)
        stats["processed"] += 1
        if not result.kept:
            stats["dropped"] += 1
            history.append({"frame_id": frame_id, "kept": False, "vision_ms": vision_ms, "spacetime_ms": 0.0})
            log.info("frame %d dropped (%s): vision %.0f ms", frame_id, result.drop_reason, vision_ms)
            return {"frame_id": frame_id, "kept": False, "reason": result.drop_reason}

        stats["kept"] += 1
        _save_frame(frame_id, jpeg)

        t0 = time.perf_counter()
        try:
            for s in result.sightings:
                st.call("add_sighting", *s.values())  # dicts are in the contract's argument order
            if result.frame:
                st.call("add_frame", *result.frame.values())
        except Exception as exc:  # Spacetime down: keep the loop going, the next frame tries again
            stats["spacetime_errors"] += 1
            log.warning("frame %d: Spacetime call failed: %s", frame_id, exc)
        spacetime_ms = (time.perf_counter() - t0) * 1000
        history.append({"frame_id": frame_id, "kept": True, "vision_ms": vision_ms, "spacetime_ms": spacetime_ms})

        seen = ", ".join(f"{s['item_id'] or '?'}@{s['furniture'] or '-'}" for s in result.sightings) or "nothing"
        log.info("frame %d kept: %s | vision %.0f ms, spacetime %.0f ms, total %.0f ms",
                 frame_id, seen, vision_ms, spacetime_ms, (time.perf_counter() - started) * 1000)
        return {"frame_id": frame_id, "kept": True, "sightings": len(result.sightings)}
    except Exception as exc:  # a bad frame must never take the loop down
        log.exception("frame failed")
        return {"error": str(exc)}
    finally:
        _busy.release()


def _sharpness(jpeg: bytes) -> float:
    """Josie's sharpness score (variance of the Laplacian) for a JPEG; 0 if it can't be decoded."""
    import cv2
    import numpy as np
    from backend.vision import gate

    grey = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_GRAYSCALE)
    return gate.sharpness(grey) if grey is not None else 0.0


async def _fetch(client: httpx.AsyncClient) -> bytes | None:
    """One JPEG from Nemo, or None (503 while Nemo records, bad reply, or no answer)."""
    try:
        r = await client.get(settings.NEMO_JPG_URL)
    except Exception as exc:  # Nemo off or out of range: the caller keeps trying
        log.warning("could not fetch a frame: %s", exc)
        return None
    if r.status_code == 503:
        # Nemo answers 503 while it's recording (button held): skip quietly.
        log.debug("GET %s -> 503 (Nemo busy recording), skipping", settings.NEMO_JPG_URL)
        return None
    if r.status_code == 200 and r.content.startswith(b"\xff\xd8"):
        return r.content
    log.warning("GET %s -> %d, not a JPEG", settings.NEMO_JPG_URL, r.status_code)
    return None


async def pull_loop() -> None:
    """FRAME_SOURCE=pull: every second, fetch a short burst of frames from Nemo and handle the sharpest.

    A single frame a second is often taken mid-step and blurred. Fetching BURST_FRAMES back to back
    (about 0.1 s apart) and keeping the sharpest gives vision a much better frame for the same
    one-a-second rate. Sharpness is scored here (about 20 ms per frame) with Josie's gate function.
    """
    log.info("pulling frames from %s once a second (sharpest of a burst of %d)",
             settings.NEMO_JPG_URL, settings.BURST_FRAMES)
    async with httpx.AsyncClient(timeout=5.0) as client:
        while True:
            started = time.monotonic()
            if _busy.locked() or answering.is_set():
                stats["skipped_busy"] += 1
            else:
                best: bytes | None = None
                best_sharp = -1.0
                scores = []
                for _ in range(max(1, settings.BURST_FRAMES)):
                    jpeg = await _fetch(client)
                    if jpeg is None:
                        break  # Nemo is busy or away: don't hammer it, try again next second
                    sharp = await asyncio.to_thread(_sharpness, jpeg)
                    scores.append(round(sharp, 1))
                    if sharp > best_sharp:
                        best, best_sharp = jpeg, sharp
                if best is not None:
                    if len(scores) > 1:
                        log.debug("burst sharpness %s -> kept %.1f", scores, best_sharp)
                    await asyncio.to_thread(handle, best)
            await asyncio.sleep(max(0.0, 1.0 - (time.monotonic() - started)))

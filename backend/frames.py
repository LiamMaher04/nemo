"""The frame loop: one JPEG in -> Josie's vision -> add_sighting / add_frame in Spacetime.

Frames arrive by POST /frame (FRAME_SOURCE=post) or by fetching NEMO_JPG_URL once a second
(FRAME_SOURCE=pull). Both call handle(). Only one frame is processed at a time: a frame that
arrives while another is still being processed is skipped, not queued.

backend.vision (and so torch/ultralytics) is imported lazily, so scripts that import backend.main
without running the app stay quick.
"""

import asyncio
import json
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
stats = {"processed": 0, "kept": 0, "dropped": 0, "skipped_busy": 0, "spacetime_errors": 0, "remote_errors": 0}

# Remote vision (VISION_URL set): backend/vision_server.py on a GPU box does process() instead of
# this laptop. A frame it doesn't answer in time is skipped; there's no switching back mid-run.
REMOTE_TIMEOUT_S = 3.0
REMOTE_WARN_EVERY_S = 30.0  # at most one warning line this often, with a count of what was skipped
_remote_client: httpx.Client | None = None
_remote_fails = 0
_remote_warned_at = 0.0


def vision_mode() -> dict[str, str]:
    """Which mode vision is in, for /health."""
    if settings.VISION_URL:
        return {"mode": "remote", "url": settings.VISION_URL}
    return {"mode": "local", "url": ""}


def _remote_failed(frame_id: int, why: str) -> None:
    """Count a skipped frame; log one warning line at most every REMOTE_WARN_EVERY_S."""
    global _remote_fails, _remote_warned_at
    stats["remote_errors"] += 1
    _remote_fails += 1
    now = time.monotonic()
    if now - _remote_warned_at >= REMOTE_WARN_EVERY_S:
        log.warning("vision server %s didn't answer frame %d (%s); skipped %d frame(s) since the last warning",
                    settings.VISION_URL, frame_id, why, _remote_fails)
        _remote_warned_at, _remote_fails = now, 0


def _remote_process(jpeg: bytes, frame_id: int, ts_ms: float) -> tuple[Any, float, float] | None:
    """POST the JPEG to {VISION_URL}/process and rebuild Josie's VisionResult from the JSON.

    Returns (result, round_trip_ms, server_ms), or None if the server failed or was too slow.
    result.ms becomes the round trip, since that's what the frame loop actually waited.
    """
    global _remote_client
    from backend.vision.areas import AreaMatch  # plain dataclasses: importing loads no model
    from backend.vision.pipeline import VisionResult

    if _remote_client is None:
        _remote_client = httpx.Client(timeout=REMOTE_TIMEOUT_S)
    started = time.perf_counter()
    try:
        r = _remote_client.post(f"{settings.VISION_URL}/process", content=jpeg,
                                headers={"Content-Type": "image/jpeg", "X-Frame-Id": str(frame_id),
                                         "X-Frame-Ts": repr(ts_ms)})
        r.raise_for_status()
        d = r.json()
        result = VisionResult(
            kept=d["kept"], drop_reason=d["drop_reason"], sharpness=d["sharpness"],
            sightings=d["sightings"], frame=d["frame"],
            furniture_boxes=[tuple(t) for t in d["furniture_boxes"]], matched_by=d["matched_by"],
            ms=d["ms"], area=AreaMatch(**d["area"]) if d.get("area") else None,
            yoloe_ms=d["yoloe_ms"], dino_ms=d["dino_ms"],
        )
    except httpx.TimeoutException:
        _remote_failed(frame_id, f"timed out after {REMOTE_TIMEOUT_S:g} s")
        return None
    except Exception as exc:
        _remote_failed(frame_id, f"{type(exc).__name__}: {exc}")
        return None
    round_trip_ms = (time.perf_counter() - started) * 1000
    result.ms = round_trip_ms
    return result, round_trip_ms, float(d.get("server_ms", d["ms"]))

# What the live page shows: the latest processed frame (kept or dropped) and exactly what vision
# returned for it. Boxes are full-frame pixels straight from YOLOE; the area is DINOv2's vote.
latest: dict[str, Any] = {}
_latest_lock = threading.Lock()


def _furniture_boxes(result: Any) -> list[dict[str, Any]]:
    """Josie's furniture_boxes as dicts. She has (name, wording, [x,y,w,h], conf); be tolerant of
    the older (name, [x,y,w,h], conf) too, so a change there never breaks the live view."""
    out = []
    for t in getattr(result, "furniture_boxes", []) or []:
        try:
            name = t[0]
            bbox = next(v for v in t if isinstance(v, (list, tuple)) and len(v) == 4)
            conf = next((v for v in reversed(t) if isinstance(v, (int, float))), 0.0)
            out.append({"name": name, "bbox": list(bbox), "conf": float(conf)})
        except Exception:
            continue
    return out


def _publish_latest(frame_id: int, ts_ms: float, jpeg: bytes, result: Any, spacetime_ms: float) -> None:
    sightings = [{k: v for k, v in s.items() if k != "thumb_b64"} for s in result.sightings]
    frame = result.frame or {}
    snapshot = {
        "frame_id": frame_id,
        "ts_ms": ts_ms,
        "kept": result.kept,
        "drop_reason": result.drop_reason,
        "sharpness": round(result.sharpness, 1),
        "sharpness_gate": _sharpness_gate(),
        "area_id": frame.get("area_id", ""),
        "area_conf": frame.get("area_conf", 0.0),
        "items_seen": json.loads(frame["items_seen_json"]) if frame.get("items_seen_json") else [],
        "sightings": sightings,
        "furniture": _furniture_boxes(result),
        "vision_ms": round(result.ms),
        "yoloe_ms": round(getattr(result, "yoloe_ms", 0) or 0),
        "dino_ms": round(getattr(result, "dino_ms", 0) or 0),
        "spacetime_ms": round(spacetime_ms),
    }
    with _latest_lock:
        latest.clear()
        latest.update(snapshot)
        latest["jpeg"] = jpeg
        if result.kept:
            _latest_kept.update({"frame_id": frame_id, "ts_ms": ts_ms, "jpeg": jpeg})


def _sharpness_gate() -> float:
    try:
        from backend.vision import settings as vs
        return float(vs.SHARPNESS_GATE)
    except Exception:
        return 0.0


def latest_state() -> dict[str, Any]:
    """The latest frame's facts without the JPEG bytes (for /live/state)."""
    with _latest_lock:
        return {k: v for k, v in latest.items() if k != "jpeg"}


def latest_jpeg() -> tuple[int, bytes] | None:
    with _latest_lock:
        if not latest:
            return None
        return latest["frame_id"], latest["jpeg"]


_latest_kept: dict[str, Any] = {}


def latest_kept() -> tuple[int, float, bytes] | None:
    """The newest KEPT frame (frame_id, ts_ms, jpeg), for the scene check."""
    with _latest_lock:
        if not _latest_kept:
            return None
        return _latest_kept["frame_id"], _latest_kept["ts_ms"], _latest_kept["jpeg"]


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
    """Load YOLOE once at startup, holding the busy lock so frames during loading are skipped.

    With VISION_URL set nothing is loaded here: it checks the vision server once and logs what
    it found. Frames are sent to it either way; any it can't answer are skipped.
    """
    global _next_frame_id
    if settings.VISION_URL:
        _next_frame_id = _first_frame_id()
        # Import the result classes now (it pulls in torch, a few seconds, but loads no model),
        # so the first frame isn't slow.
        from backend.vision.areas import AreaMatch  # noqa: F401
        from backend.vision.pipeline import VisionResult  # noqa: F401
        try:
            h = httpx.get(f"{settings.VISION_URL}/health", timeout=5.0).json()
            remote_health.clear()
            remote_health.update(h)
            log.info("vision is REMOTE at %s: loaded=%s on %s%s, %d area and %d item reference folders "
                     "(next frame_id %d)", settings.VISION_URL, h.get("loaded"), h.get("device"),
                     f" ({h['gpu']})" if h.get("gpu") else "", len(h.get("area_refs", {})),
                     len(h.get("item_refs", {})), _next_frame_id)
        except Exception as exc:
            log.warning("vision is REMOTE at %s but its /health didn't answer (%s): frames are skipped "
                        "until it does. Blank VISION_URL and restart to run vision here.", settings.VISION_URL, exc)
        return
    with _busy:
        started = time.perf_counter()
        from backend.vision import pipeline
        pipeline.load()  # YOLOE, DINOv2 and the reference fingerprints, so the first frame isn't ~25 s
        _next_frame_id = _first_frame_id()
        log.info("vision ready in %.1f s (next frame_id %d)", time.perf_counter() - started, _next_frame_id)


remote_health: dict[str, Any] = {}  # the vision server's /health at startup (VISION_URL set)


def vision_status() -> dict[str, Any]:
    """What /health reports about vision: models loaded, device, reference photos."""
    import sys
    if settings.VISION_URL:
        h = remote_health
        return {"ready": bool(h.get("loaded")), "yoloe": bool(h.get("loaded")), "dinov2": bool(h.get("loaded")),
                "device": h.get("device"), "refs_dir": h.get("refs_dir"),
                "area_refs": len(h.get("area_refs", {})), "item_refs": len(h.get("item_refs", {})),
                "note": "from the vision server's /health at startup" if h else "vision server didn't answer"}
    det = sys.modules.get("backend.vision.detector")
    dino = sys.modules.get("backend.vision.dino")
    areas = sys.modules.get("backend.vision.areas")
    items = sys.modules.get("backend.vision.item_match")
    from backend.vision import settings as vs
    pipe = sys.modules.get("backend.vision.pipeline")
    yoloe_ok = bool(det and det._model is not None)
    dino_ok = bool(dino and dino._model is not None)
    # Ready only once pipeline.load() has finished, reference fingerprints included.
    return {"ready": bool(pipe and pipe._loaded), "yoloe": yoloe_ok, "dinov2": dino_ok,
            "device": det._device if det else None, "refs_dir": str(vs.REFS_DIR),
            "area_refs": len(areas._refs) if areas else 0, "item_refs": len(items._refs) if items else 0}


def handle(jpeg: bytes) -> dict[str, Any]:
    """Process one frame if nothing else is being processed. Never raises."""
    global _next_frame_id
    # Every frame Nemo returns goes to the fall check first, whatever vision then does with it.
    try:
        from backend import fall
        fall.observe(jpeg)
    except Exception as exc:
        log.warning("fall check failed: %s", exc)
    if answering.is_set():
        stats["skipped_busy"] += 1
        return {"skipped": "answering"}
    if not _busy.acquire(blocking=False):
        stats["skipped_busy"] += 1
        return {"skipped": "busy"}
    try:
        started = time.perf_counter()
        if _next_frame_id == 0:
            _next_frame_id = _first_frame_id()
        frame_id = _next_frame_id
        _next_frame_id += 1
        ts_ms = time.time() * 1000

        if settings.VISION_URL:
            got = _remote_process(jpeg, frame_id, ts_ms)
            if got is None:
                return {"frame_id": frame_id, "skipped": "vision server"}
            result, round_trip_ms, server_ms = got
            timing = (f"vision {round_trip_ms:.0f} ms (server {server_ms:.0f} ms, "
                      f"network {max(0.0, round_trip_ms - server_ms):.0f} ms)")
        else:
            from backend.vision import process
            result = process(jpeg, frame_id, ts_ms)
            timing = f"vision {result.ms:.0f} ms"
        vision_ms = result.ms
        _vision_ms.append(vision_ms)
        stats["processed"] += 1
        if not result.kept:
            stats["dropped"] += 1
            history.append({"frame_id": frame_id, "ts_ms": ts_ms, "kept": False, "reason": result.drop_reason,
                            "sharpness": round(result.sharpness, 1), "vision_ms": vision_ms, "spacetime_ms": 0.0,
                            "seen": []})
            try:
                _publish_latest(frame_id, ts_ms, jpeg, result, 0.0)
            except Exception as exc:  # the live view must never take the pipeline down
                log.warning("live view snapshot failed: %s", exc)
            log.info("frame %d dropped (%s): %s", frame_id, result.drop_reason, timing)
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
        seen_list = [{"item_id": s["item_id"], "label": s["label"], "furniture": s["furniture"],
                      "conf": s["det_conf"]} for s in result.sightings]
        history.append({"frame_id": frame_id, "ts_ms": ts_ms, "kept": True, "reason": "",
                        "sharpness": round(result.sharpness, 1), "vision_ms": vision_ms,
                        "spacetime_ms": spacetime_ms, "seen": seen_list,
                        "area_id": (result.frame or {}).get("area_id", "")})
        try:
            _publish_latest(frame_id, ts_ms, jpeg, result, spacetime_ms)
        except Exception as exc:  # the live view must never take the pipeline down
            log.warning("live view snapshot failed: %s", exc)

        # Super VL, in the background: second opinions on unsure boxes, and a description of the
        # spot for anything Spacetime just placed. Returns at once; the work happens on its own thread.
        try:
            from backend import vl
            vl.after_frame(frame_id, ts_ms, jpeg, result.sightings)
        except Exception as exc:
            log.warning("super vl hook failed: %s", exc)

        seen = ", ".join(f"{s['item_id'] or '?'}@{s['furniture'] or '-'}" for s in result.sightings) or "nothing"
        log.info("frame %d kept: %s | %s, spacetime %.0f ms, total %.0f ms",
                 frame_id, seen, timing, spacetime_ms, (time.perf_counter() - started) * 1000)
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
        log.warning("could not fetch a frame from %s: %s %s", settings.NEMO_JPG_URL, type(exc).__name__, exc)
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

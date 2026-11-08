"""Nemo backend: receives frames from the device.

Run from the repo root:  python -m backend.main
"""

import logging
import os
import time
from collections import deque

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from backend import agent, settings

log = logging.getLogger("nemo.backend")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

app = FastAPI(title="Nemo backend")

FPS_WINDOW_S = 10.0  # frames per second is averaged over the last 10 seconds

frames_received = 0
recent_frame_times: deque[float] = deque()
last_frame_at: float | None = None
last_device_id: str | None = None


def _frames_per_second(now: float) -> float:
    while recent_frame_times and now - recent_frame_times[0] > FPS_WINDOW_S:
        recent_frame_times.popleft()
    return round(len(recent_frame_times) / FPS_WINDOW_S, 2)


@app.get("/health")
def health() -> dict:
    now = time.time()
    return {
        "ok": True,
        "frames_received": frames_received,
        "fps": _frames_per_second(now),
        "seconds_since_last_frame": round(now - last_frame_at, 1) if last_frame_at else None,
        "last_device_id": last_device_id,
    }


@app.post("/frame")
async def frame(request: Request) -> dict:
    global frames_received, last_frame_at, last_device_id

    started = time.perf_counter()
    body = await request.body()
    if not body.startswith(b"\xff\xd8"):
        raise HTTPException(status_code=400, detail="Body is not a JPEG")

    settings.CAPTURES_DIR.mkdir(parents=True, exist_ok=True)
    tmp = settings.LATEST_FRAME.with_suffix(".tmp")
    tmp.write_bytes(body)
    os.replace(tmp, settings.LATEST_FRAME)  # swap in whole, so readers never see half a file

    now = time.time()
    frames_received += 1
    recent_frame_times.append(now)
    last_frame_at = now
    last_device_id = request.headers.get("X-Device-Id")

    log.info(
        "frame %d from %s: %d bytes, saved in %.1f ms",
        frames_received,
        last_device_id or "unknown",
        len(body),
        (time.perf_counter() - started) * 1000,
    )
    return {"ok": True}


class AskText(BaseModel):
    question: str


@app.post("/ask_text")
async def ask_text(body: AskText) -> dict:
    """Text in, text out: the agent answers a question. Tool calls and timing are logged by agent.ask."""
    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="question is empty")
    try:
        result = await run_in_threadpool(agent.ask, question)
    except RuntimeError as exc:
        log.error("ask_text failed: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc))
    return {"answer": result["answer"], "tool_calls": result["tool_calls"]}


if __name__ == "__main__":
    uvicorn.run(app, host=settings.BACKEND_HOST, port=settings.BACKEND_PORT)

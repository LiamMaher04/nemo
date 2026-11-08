"""Nemo backend: frames from the device, and questions answered out loud.

Run from the repo root:  python -m backend.main
"""

import asyncio
import logging
import os
import time
from collections import deque
from contextlib import asynccontextmanager
from urllib.parse import quote

import uvicorn
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from backend import agent, alerts, frames, settings, spacetime_client, speech

log = logging.getLogger("nemo.backend")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

speech_error: str | None = "speech not loaded yet"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Load the speech models once at startup. If that fails, /ask says why and the rest still runs."""
    global speech_error
    started = time.perf_counter()
    try:
        await run_in_threadpool(speech.load)
        speech_error = None
        log.info("speech ready (TTS_PROVIDER=%s) in %.1f s", settings.TTS_PROVIDER, time.perf_counter() - started)
    except Exception as exc:
        speech_error = str(exc)
        log.error("speech failed to load, /ask is off: %s", exc)

    # Carer alerts: make sure Spacetime's check_alerts is scheduled, then text whatever it raises.
    try:
        await run_in_threadpool(spacetime_client.call, "start_alert_checks")
    except Exception as exc:
        log.warning("could not schedule check_alerts in Spacetime: %s", exc)
    sender = asyncio.create_task(alerts.sender_loop())

    # Vision: load YOLOE in the background (frames that arrive meanwhile are skipped), then pull
    # frames from Nemo if FRAME_SOURCE=pull. POST /frame works either way.
    background = [sender, asyncio.create_task(asyncio.to_thread(frames.warm_up))]
    if settings.FRAME_SOURCE == "pull":
        if settings.NEMO_JPG_URL:
            background.append(asyncio.create_task(frames.pull_loop()))
        else:
            log.error("FRAME_SOURCE=pull but NEMO_JPG_URL is empty: not pulling frames")
    yield
    for task in background:
        task.cancel()


app = FastAPI(title="Nemo backend", lifespan=lifespan)

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
        "frame_source": settings.FRAME_SOURCE,
        "vision": {**frames.stats, "avg_vision_ms_last_20": frames.avg_vision_ms()},
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

    # Vision runs in the background so Nemo isn't kept waiting. Busy = skip this frame.
    if frames._busy.locked():
        frames.stats["skipped_busy"] += 1
        return {"ok": True, "skipped": "busy"}
    asyncio.create_task(asyncio.to_thread(frames.handle, body))
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


NOT_HEARD = "Sorry, I didn't catch that. Hold the button and ask again."
CANT_ANSWER = "Sorry, I can't answer that right now."


@app.post("/ask")
async def ask(request: Request) -> Response:
    """WAV in (16 kHz mono 16-bit), spoken answer out as a WAV in the same format."""
    if speech_error:
        raise HTTPException(status_code=503, detail=f"speech not available: {speech_error}")
    body = await request.body()
    if not body.startswith(b"RIFF"):
        raise HTTPException(status_code=400, detail="Body is not a WAV")

    t0 = time.perf_counter()
    frames.answering.set()  # pause vision so speech to text and the agent get the CPU
    try:
        try:
            question = await run_in_threadpool(speech.transcribe, body)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"could not read the audio: {exc}")
        t1 = time.perf_counter()

        if not question:
            answer = NOT_HEARD
        else:
            try:
                answer = (await run_in_threadpool(agent.ask, question))["answer"]
            except Exception as exc:  # still say something out loud rather than go silent
                log.error("agent failed: %s", exc)
                answer = CANT_ANSWER
        t2 = time.perf_counter()

        wav, voice = await run_in_threadpool(speech.speak, answer)
        t3 = time.perf_counter()
    finally:
        frames.answering.clear()

    log.info(
        "ask from %s: stt %.0f ms, agent %.0f ms, tts %.0f ms (%s), total %.0f ms | Q=%r A=%r",
        request.headers.get("X-Device-Id", "unknown"),
        (t1 - t0) * 1000, (t2 - t1) * 1000, (t3 - t2) * 1000, voice, (t3 - t0) * 1000,
        question, answer,
    )
    return Response(
        content=wav,
        media_type="audio/wav",
        headers={  # percent-encoded UTF-8, since HTTP headers can't carry every character
            "X-Question-Text": quote(question),
            "X-Answer-Text": quote(answer),
            "X-Voice": voice,
        },
    )


if __name__ == "__main__":
    uvicorn.run(app, host=settings.BACKEND_HOST, port=settings.BACKEND_PORT)

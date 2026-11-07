"""Nemo backend. Run from the repo root:  uvicorn backend.app.main:app --host 0.0.0.0 --port 8000"""
from __future__ import annotations

import json
import logging
import time
from collections import deque
from typing import Any

from fastapi import FastAPI, Request
from pydantic import BaseModel

from . import config, nemotron, spacetime, vision

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
log = logging.getLogger("nemo")
app = FastAPI(title="Nemo backend")

_frame_times: deque[float] = deque(maxlen=30)
_frame_id = 0


@app.get("/health")
def health() -> dict[str, Any]:
    fps = 0.0
    if len(_frame_times) > 1:
        fps = (len(_frame_times) - 1) / (_frame_times[-1] - _frame_times[0])
    return {"ok": True, "frames": _frame_id, "fps": round(fps, 2)}


@app.post("/frame")
async def frame(request: Request) -> dict[str, Any]:
    global _frame_id
    jpeg = await request.body()
    _frame_id += 1
    now = time.time()
    _frame_times.append(now)
    (config.CAPTURES_DIR / "latest.jpg").write_bytes(jpeg)
    if _frame_id % 10 == 0:
        log.info("frame %d, %d bytes, %.2f fps", _frame_id, len(jpeg), health()["fps"])

    t0 = time.perf_counter()
    sightings = vision.process(jpeg, _frame_id, now * 1000)
    for s in sightings:
        try:
            spacetime.add_sighting(s)
        except Exception as e:
            log.warning("add_sighting failed: %s", e)
    if sightings:
        log.info("frame %d: %d sightings in %.0f ms", _frame_id, len(sightings),
                 (time.perf_counter() - t0) * 1000)
    return {"ok": True}


class Coverage(BaseModel):
    device_id: str = "nemo-a"
    state: str = "recording"
    reason: str = ""


@app.post("/coverage")
def coverage(c: Coverage) -> dict[str, Any]:
    spacetime.call("set_coverage", c.device_id, c.state, c.reason, time.time() * 1000)
    return {"ok": True}


class Question(BaseModel):
    question: str


def _resolve_item(question: str) -> dict[str, Any] | None:
    """Crude first version: match item names/aliases in the question. The agent replaces this."""
    q = question.lower()
    for item in spacetime.sql("SELECT * FROM items"):
        names = [item["display_name"], item["item_id"].replace("_", " ")]
        try:
            names += json.loads(item.get("aliases_json") or "[]")
        except json.JSONDecodeError:
            pass
        if any(n and n.lower() in q for n in names):
            return item
    return None


def _ago(ts_ms: float) -> str:
    mins = int((time.time() * 1000 - ts_ms) / 60000)
    if mins < 1:
        return "just now"
    if mins < 60:
        return f"{mins} minutes ago"
    return f"about {mins // 60} hours ago"


@app.post("/ask_text")
def ask_text(q: Question) -> dict[str, Any]:
    t0 = time.perf_counter()
    item = _resolve_item(q.question)
    if not item:
        return {"answer": "Sorry, I'm not sure which item you mean.", "item_id": None}
    state = spacetime.where_is(item["item_id"])
    if not state or not state.get("last_placed_room"):
        facts = f"No record yet of where the {item['display_name']} was put down."
    else:
        facts = (f"Item: {item['display_name']}. Last put down in room '{state['last_placed_room']}'"
                 f", spot '{state['last_placed_anchor'] or 'unknown'}'"
                 f" ({state['last_placed_relation'] or 'at'}), {_ago(state['last_placed_ts_ms'])}. "
                 f"Current state: {state['state']}. Confidence {state['confidence']:.2f}.")
    answer = nemotron.say([
        {"role": "system", "content": "You are Nemo, a kind memory helper for an older person. "
         "Answer in one short spoken sentence using only the facts given. If confidence is below "
         "0.5, say you're not sure. Never invent places."},
        {"role": "user", "content": f"Question: {q.question}\nFacts: {facts}"},
    ])
    log.info("ask_text in %.0f ms", (time.perf_counter() - t0) * 1000)
    return {"answer": answer, "item_id": item["item_id"],
            "has_snapshot": bool(state and state.get("last_placed_thumb_b64"))}


# TODO: POST /ask (audio in, WAV out): faster-whisper -> ask_text logic -> TTS. See docs/interfaces.md.

"""Nemotron Super VL: a second pair of eyes for the memory and the agent.

Four jobs, all off the hot path:
- describe_spot: after Spacetime confirms a placement, say where exactly the item is
  ("on the desk between the lamp and the water bottles"). Written to item_state.spot_description.
- second_opinion: when vision is unsure between look-alikes, pick one (or none) from a tight crop.
- answer_about: the agent's look_at_snapshot tool, only called when the agent has a reason.
- scene_indoors: once a minute, indoors or outdoors, so Spacetime can raise "left the house".

Latency rules: one background worker thread, one Super VL call at a time, images downscaled to
448 to 640 px (15 to 30 KB), thinking off, short answers, a hard timeout, and a small queue that
drops work rather than piling it up. Measured: about 0.9 to 1.6 s per call.
"""

import base64
import json
import logging
import queue
import threading
import time
from typing import Any, Callable

import cv2
import numpy as np
from openai import OpenAI

from backend import settings
from backend import spacetime_client as st

log = logging.getLogger("nemo.vl")

QUEUE_SIZE = 4  # pending background jobs; anything more is dropped (the next frame brings new ones)

stats: dict[str, Any] = {"calls": 0, "failed": 0, "dropped": 0, "avg_ms": None, "last": ""}
_ms: list[float] = []


# ---- Model ----

_provider_cache: list[tuple[str, OpenAI, str, dict[str, Any]]] | None = None


def _providers() -> list[tuple[str, OpenAI, str, dict[str, Any]]]:
    """The API clients, built once. A fresh client per call cost a TLS handshake (about a second)
    every time; a shared one keeps the connection open. OpenAI clients are thread-safe."""
    global _provider_cache
    if _provider_cache is not None:
        return _provider_cache
    out = []
    if settings.NEMOTRON_API_KEY and settings.NEMOTRON_VL_MODEL:
        # max_retries=0: the SDK's default of 2 retries turned one slow call into 40 s or more.
        # OpenRouter below is the retry; a job that still fails is dropped, not queued.
        out.append(("nvidia", OpenAI(base_url=settings.NEMOTRON_BASE_URL, api_key=settings.NEMOTRON_API_KEY,
                                     max_retries=0),
                    settings.NEMOTRON_VL_MODEL, {"chat_template_kwargs": {"enable_thinking": False}}))
    if settings.OPENROUTER_API_KEY and settings.OPENROUTER_VL_MODEL:
        out.append(("openrouter", OpenAI(base_url=settings.OPENROUTER_BASE_URL, api_key=settings.OPENROUTER_API_KEY,
                                         max_retries=0),
                    settings.OPENROUTER_VL_MODEL, {"reasoning": {"enabled": False}}))
    _provider_cache = out
    return out


def ask_image(jpeg: bytes, prompt: str, max_tokens: int = 40, timeout_s: float | None = None) -> str:
    """One Super VL call: image + question -> short text. Raises on failure."""
    providers = _providers()
    if not providers:
        raise RuntimeError("Super VL needs NEMOTRON_API_KEY and NEMOTRON_VL_MODEL (or OpenRouter) in .env")
    b64 = base64.b64encode(jpeg).decode("ascii")
    started = time.perf_counter()
    last_error: Exception | None = None
    for name, client, model, extra in providers:
        try:
            r = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                    {"type": "text", "text": prompt},
                ]}],
                max_tokens=max_tokens,
                temperature=0.0,
                extra_body=extra,
                timeout=timeout_s or settings.VL_TIMEOUT_S,
            )
            text = (r.choices[0].message.content or "").strip()  # never the reasoning, only the answer
            ms = (time.perf_counter() - started) * 1000
            _ms.append(ms)
            del _ms[:-20]
            stats["calls"] += 1
            stats["avg_ms"] = round(sum(_ms) / len(_ms))
            stats["last"] = text[:80]
            log.info("super vl (%s) %.0f ms: %r", name, ms, text[:120])
            return text
        except Exception as exc:
            last_error = exc
            log.warning("super vl via %s failed: %s", name, exc)
    stats["failed"] += 1
    raise RuntimeError(f"Super VL failed: {last_error}")


# ---- Images ----

def _decode(jpeg: bytes) -> np.ndarray | None:
    return cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)


def _encode(bgr: np.ndarray, max_side: int) -> bytes:
    h, w = bgr.shape[:2]
    scale = min(1.0, max_side / max(h, w))
    if scale < 1.0:
        bgr = cv2.resize(bgr, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", bgr, [cv2.IMWRITE_JPEG_QUALITY, 80])
    return buf.tobytes() if ok else b""


def _bbox(bbox_json: str) -> tuple[int, int, int, int] | None:
    try:
        x, y, w, h = [int(round(v)) for v in json.loads(bbox_json)]
        return (x, y, w, h) if w > 0 and h > 0 else None
    except Exception:
        return None


def crop_around(jpeg: bytes, bbox_json: str, pad: float, max_side: int, highlight: bool) -> bytes | None:
    """A crop around the item box, padded by `pad` times its size, optionally with the box drawn on it.

    The highlight is how we tell Super VL WHICH object we mean when the crop shows several.
    """
    img = _decode(jpeg)
    box = _bbox(bbox_json)
    if img is None or box is None:
        return None
    H, W = img.shape[:2]
    x, y, w, h = box
    px, py = int(w * pad), int(h * pad)
    x1, y1 = max(0, x - px), max(0, y - py)
    x2, y2 = min(W, x + w + px), min(H, y + h + py)
    crop = img[y1:y2, x1:x2].copy()
    if highlight:
        t = max(2, int(min(crop.shape[:2]) / 120))
        cv2.rectangle(crop, (x - x1, y - y1), (x - x1 + w, y - y1 + h), (80, 255, 120), t)
    return _encode(crop, max_side)


def whole_frame(jpeg: bytes, max_side: int = 512) -> bytes | None:
    img = _decode(jpeg)
    return _encode(img, max_side) if img is not None else None


# ---- The four questions ----

def _clean_sentence(text: str, max_chars: int = 140) -> str:
    text = text.strip().strip('"').strip("'").replace("\n", " ")
    if len(text) > max_chars:
        text = text[:max_chars].rsplit(" ", 1)[0]
    return text.rstrip(". ")


def describe_spot(jpeg: bytes, bbox_json: str, item_name: str, furniture: str = "", area: str = "") -> str:
    """Where exactly the highlighted item is, in one spoken sentence. "" if it can't be done.

    `furniture` is what Spacetime says it's on (from YOLOE), so the description uses the same word
    the rest of the answer does ("on the desk ...", not "on the counter ..."). `area` is the
    fallback hint when no furniture was in view.
    """
    crop = crop_around(jpeg, bbox_json, pad=2.5, max_side=640, highlight=True)
    if not crop:
        return ""
    if furniture:
        on = f" It is on the {furniture.replace('_', ' ')}."
    elif area:
        on = f" It is in the {area.replace('_', ' ')} area."
    else:
        on = ""
    prompt = (f"The object inside the green box is the person's {item_name}.{on} In one short spoken "
              f"sentence of at most 14 words, say exactly where it is using the things around it, for "
              f"example 'on the desk between the lamp and the water bottles'. Start with 'on', 'by', 'in' "
              f"or 'under'. Don't mention the box, the photo or the {item_name} itself. If you can't "
              f"see clearly where it is, answer 'unclear'.")
    text = _clean_sentence(ask_image(crop, prompt, max_tokens=40))
    return "" if is_unclear(text) else text


_UNCLEAR = ("unclear", "can't tell", "cannot tell", "can't see", "cannot see", "not sure", "unsure")


def is_unclear(description: str) -> bool:
    """An empty or "unclear" spot description: not worth storing, worth another try."""
    d = description.strip().lower()
    return not d or any(u in d for u in _UNCLEAR)


def second_opinion(jpeg: bytes, bbox_json: str, candidates: list[tuple[str, str]]) -> str:
    """candidates: [(item_id, spoken name)]. Returns the chosen item_id, or "" if none / unsure."""
    crop = crop_around(jpeg, bbox_json, pad=0.6, max_side=448, highlight=False)
    if not crop or not candidates:
        return ""
    names = [n for _, n in candidates]
    options = ", ".join(names) + ", none of them, or unsure"
    prompt = (f"Which of these is the main object in this photo: {options}? "
              f"If the photo is too small, dark or blurry to tell clearly, answer 'unsure'. "
              f"Answer with exactly one of those options and nothing else.")
    answer = ask_image(crop, prompt, max_tokens=8).lower().strip(" .")
    if "unsure" in answer or "none" in answer:
        return ""
    for item_id, name in candidates:
        if name.lower() in answer:
            return item_id
    return ""


def scene_indoors(jpeg: bytes) -> bool | None:
    """True indoors, False outdoors, None if unsure or failed."""
    img = whole_frame(jpeg, 512)
    if not img:
        return None
    answer = ask_image(img, "Is this photo taken indoors or outdoors? Answer with exactly one word: "
                            "indoors or outdoors.", max_tokens=4).lower()
    if "outdoor" in answer:
        return False
    if "indoor" in answer:
        return True
    return None


def answer_about(jpeg: bytes, bbox_json: str | None, item_name: str, question: str) -> str:
    """The agent's look_at_snapshot: answer a question about the item from the frame."""
    if bbox_json:
        img = crop_around(jpeg, bbox_json, pad=2.5, max_side=640, highlight=True)
        lead = f"The object inside the green box is the person's {item_name}. "
    else:
        img = whole_frame(jpeg, 640)
        lead = ""
    if not img:
        return ""
    prompt = (f"{lead}{question} Answer in one short spoken sentence of at most 20 words, only from what "
              f"you can actually see. Don't mention the box or the photo.")
    return _clean_sentence(ask_image(img, prompt, max_tokens=60, timeout_s=8), max_chars=200)


FALL_PROMPT = ("Does this look like a floor or ceiling seen by someone who has fallen, or a camera lying "
               "face down? Answer yes or no.")


def fall_check_job(jpeg: bytes, ts_ms: float) -> bool:
    """backend/fall.py saw a long run of dark or still, featureless frames: does Super VL agree?

    Yes -> Spacetime's report_possible_fall raises the carer alert (at most one every 30 minutes).
    """
    img = whole_frame(jpeg, 512)
    if not img:
        return False
    answer = ask_image(img, FALL_PROMPT, max_tokens=4).strip().lower()
    yes = answer.startswith("yes")
    log.info("super vl fall check: %r -> %s", answer, "possible fall reported" if yes else "not a fall")
    if yes:
        st.call("report_possible_fall", ts_ms)
    return yes


# ---- Background worker: one Super VL call at a time, never blocking frames or answers ----

_jobs: queue.Queue = queue.Queue(maxsize=QUEUE_SIZE)
_worker_started = False
_in_flight: set[str] = set()  # job keys queued or running, so the same item isn't asked twice


def _worker() -> None:
    while True:
        key, fn, args = _jobs.get()
        try:
            fn(*args)
        except Exception as exc:
            log.warning("super vl job %s failed: %s", key, exc)
        finally:
            _in_flight.discard(key)
            _jobs.task_done()


def submit(key: str, fn: Callable, *args: Any) -> bool:
    """Queue a background job. False if dropped (queue full or the same key is already pending)."""
    global _worker_started
    if not _worker_started:
        threading.Thread(target=_worker, name="super-vl", daemon=True).start()
        _worker_started = True
    if key in _in_flight:
        return False
    try:
        _jobs.put_nowait((key, fn, args))
        _in_flight.add(key)
        return True
    except queue.Full:
        stats["dropped"] += 1
        return False


# ---- Jobs wired to the frame loop ----

def _item_names() -> dict[str, str]:
    from backend import agent
    return {it["item_id"]: it["name"] for it in agent._items()}


def _describe_job(item_id: str, placed_ts_ms: float, jpeg: bytes, bbox_json: str, furniture: str = "",
                  area: str = "") -> None:
    text = describe_spot(jpeg, bbox_json, _item_names().get(item_id, item_id.replace("_", " ")), furniture, area)
    if text:
        st.call("set_spot_description", item_id, placed_ts_ms, text)
        log.info("spot described: %s -> %r", item_id, text)
    else:
        log.info("spot description for %s came back empty or unclear (try %d of %d)", item_id,
                 _describe_tries.get((item_id, placed_ts_ms), 1), DESCRIBE_TRIES)


MIN_BOX_PX = 80  # a box smaller than this (longest side) is too little to identify from; don't ask
PICK_REPEAT_MS = 20_000  # a Super VL pick nobody else supports counts once it repeats within this long
_last_pick: dict[str, tuple[Any, float, str]] = {}  # item_id -> (frame_id, ts_ms, YOLOE label) of the last pick

# When DINOv2 is unsure and Super VL can't tell either, YOLOE's own wording may still place these
# items, if YOLOE was reasonably confident. Only the pill bottle (item_id pill_box): it's the item
# the reminders and the carer alerts depend on, and YOLOE's pill-bottle wordings don't look like
# anything else we track.
# The sighting still goes through add_sighting, so CONFIRM_FRAMES (2 in a row) still applies.
YOLOE_FALLBACK_ITEMS = {"pill_box"}
YOLOE_FALLBACK_MIN_CONF = 0.30  # YOLOE confidence needed (DETECT_CONF, the floor, is 0.20)


def _label_item(label: str, names: dict[str, str]) -> str:
    """The item_id YOLOE's wording points at ("pill bottle with white cap" -> pill_box), or ""."""
    try:
        from backend.vision import classes
        for item_id, wordings in classes.ITEMS.items():
            if label in wordings and item_id in names:
                return item_id
    except Exception:
        pass
    return ""


def _report_identified(sighting: dict[str, Any], item_id: str, jpeg: bytes) -> None:
    """Re-report an unsure sighting as this item. Spacetime keeps the unsure one too (append-only)
    and its placement rules (CONFIRM_FRAMES and all) still decide what goes into item_state."""
    resolved = {**sighting, "item_id": item_id, "match_margin": 1.0,
                "candidates_json": json.dumps([[item_id, 1.0]])}
    st.call("add_sighting", *resolved.values())
    # If that sighting made Spacetime place the item, describe the spot (same check as after_frame).
    _describe_if_just_placed({item_id: resolved}, sighting["ts_ms"], jpeg)


def _yoloe_fallback(sighting: dict[str, Any], label_item: str, jpeg: bytes, why: str) -> bool:
    """Super VL couldn't tell: trust YOLOE's wording for the pill bottle if YOLOE was confident enough."""
    if label_item not in YOLOE_FALLBACK_ITEMS or sighting["det_conf"] < YOLOE_FALLBACK_MIN_CONF:
        return False
    _report_identified(sighting, label_item, jpeg)
    log.info("yoloe fallback: %r is the %s (det %.2f, super vl %s, frame %s)",
             sighting["label"], label_item, sighting["det_conf"], why, sighting["frame_id"])
    return True


def _second_opinion_job(sighting: dict[str, Any], jpeg: bytes) -> None:
    names = _item_names()
    label_item = _label_item(sighting["label"], names)
    box = _bbox(sighting["bbox_json"])
    if not box or max(box[2], box[3]) < MIN_BOX_PX:
        if not _yoloe_fallback(sighting, label_item, jpeg, "not asked, box too small"):
            log.info("super vl second opinion skipped: box too small (%s)", sighting["bbox_json"])
        return
    try:
        cands = json.loads(sighting["candidates_json"])
    except Exception:
        return
    dino = [c[0] for c in cands if isinstance(c, list) and c and c[0] in names]
    # Offer every tracked item, most likely first: YOLOE's wording, DINOv2's guesses, then the rest.
    # (Only offering DINOv2's guesses meant Super VL could never name the wallet when both missed it.)
    ordered: list[str] = []
    for i in ([label_item] if label_item else []) + dino + list(names):
        if i and i not in ordered:
            ordered.append(i)
    options = [(i, names[i]) for i in ordered]
    if not options:
        return
    try:
        chosen = second_opinion(jpeg, sighting["bbox_json"], options)
    except Exception as exc:
        if not _yoloe_fallback(sighting, label_item, jpeg, "failed"):
            raise
        log.warning("super vl second opinion failed (%s); used YOLOE's wording", exc)
        return
    if not chosen:
        if not _yoloe_fallback(sighting, label_item, jpeg, "unsure"):
            log.info("super vl second opinion: unsure (frame %s, %s)", sighting["frame_id"], sighting["label"])
        return
    # A lone Super VL guess on a blurry crop is not enough to go into memory. Accept it if it agrees
    # with YOLOE's wording or DINOv2's best guess, OR if Super VL gave the same answer for the same
    # kind of box (same YOLOE wording) on a previous frame (two frames agreeing is independent
    # evidence). The wording check stops a wallet picked on one box carrying over to a different box.
    supported = {label_item, dino[0] if dino else ""} - {""}
    prev = _last_pick.get(chosen)
    repeated = (prev is not None and prev[0] != sighting["frame_id"] and prev[2] == sighting["label"]
                and sighting["ts_ms"] - prev[1] <= PICK_REPEAT_MS)
    _last_pick[chosen] = (sighting["frame_id"], sighting["ts_ms"], sighting["label"])
    if chosen not in supported and not repeated:
        log.info("super vl second opinion: said %s (YOLOE %s, DINOv2 %s); waiting for a second frame to agree",
                 chosen, label_item or "-", dino[0] if dino else "-")
        return
    _report_identified(sighting, chosen, jpeg)
    log.info("super vl second opinion: %r is the %s (frame %s)", sighting["label"], chosen, sighting["frame_id"])


DESCRIBE_TRIES = 3  # Super VL tries per placement while the description is empty or "unclear"
DESCRIBE_WINDOW_MS = 60_000  # ... and only while the item is seen within this long of being placed
_describe_tries: dict[tuple[str, float], int] = {}  # (item_id, last_placed_ts_ms) -> tries so far


def _describe_if_just_placed(seen: dict[str, dict[str, Any]], ts_ms: float, jpeg: bytes) -> None:
    """Queue a spot description for items in `seen` (seen in this frame) whose current placement
    has no usable description yet: the frame that placed them, then later frames of the same spot
    within DESCRIBE_WINDOW_MS, up to DESCRIBE_TRIES tries per placement."""
    if not seen:
        return
    where = " OR ".join(f"item_id = '{i}'" for i in seen)
    try:
        rows = st.sql(f"SELECT * FROM item_state WHERE {where}")
    except Exception as exc:
        log.warning("could not read item_state for spot descriptions: %s", exc)
        return
    for r in rows:
        s = seen[r["item_id"]]
        placed = r["last_placed_ts_ms"]
        if not is_unclear(r["spot_description"]):
            continue  # already described
        if not (placed - 1.0 <= ts_ms <= placed + DESCRIBE_WINDOW_MS):
            continue  # too long after it was put down
        if s.get("area_id", r["area_id"]) != r["area_id"] or s.get("furniture", r["furniture"]) != r["furniture"]:
            continue  # this frame shows it somewhere else (it may be moving): don't describe the old spot
        key = (r["item_id"], placed)
        if _describe_tries.get(key, 0) >= DESCRIBE_TRIES:
            continue
        if submit(f"describe:{r['item_id']}", _describe_job, r["item_id"], placed, jpeg,
                  s["bbox_json"], r.get("furniture", ""), r.get("area_id", "")):
            _describe_tries[key] = _describe_tries.get(key, 0) + 1
    if len(_describe_tries) > 200:  # forget old placements
        for k in [k for k in _describe_tries if ts_ms - k[1] > DESCRIBE_WINDOW_MS]:
            _describe_tries.pop(k, None)


def after_frame(frame_id: int, ts_ms: float, jpeg: bytes, sightings: list[dict[str, Any]]) -> None:
    """Called by the frame loop after a kept frame's sightings went to Spacetime. Returns quickly."""
    if not settings.SUPER_VL:
        return
    # Second opinions for unsure sightings that have candidates (at most 2 per frame).
    if settings.VL_SECOND_OPINION:
        def box_area(s: dict[str, Any]) -> int:
            b = _bbox(s["bbox_json"])
            return b[2] * b[3] if b else 0

        # Biggest boxes first: they're the ones Super VL has a real chance of identifying.
        unsure = sorted((s for s in sightings if s["item_id"] == "" and box_area(s) >= MIN_BOX_PX * MIN_BOX_PX // 2),
                        key=box_area, reverse=True)
        for s in unsure[:2]:
            submit(f"opinion:{frame_id}:{s['bbox_json']}", _second_opinion_job, s, jpeg)
    # Spot descriptions for items Spacetime just placed from this frame.
    _describe_if_just_placed({s["item_id"]: s for s in sightings if s["item_id"]}, ts_ms, jpeg)


# ---- Scene check: indoors or outdoors, once a minute ----

def scene_loop(latest_kept: Callable[[], tuple[int, float, bytes] | None]) -> None:
    """Every VL_SCENE_EVERY_S, look at the newest kept frame and tell Spacetime indoors/outdoors."""
    if not (settings.SUPER_VL and settings.VL_SCENE_CHECK):
        log.info("scene check off")
        return
    log.info("scene check (indoors/outdoors) every %d s", settings.VL_SCENE_EVERY_S)
    last_frame = -1
    while True:
        time.sleep(settings.VL_SCENE_EVERY_S)
        got = latest_kept()
        if not got or got[0] == last_frame:
            continue  # no new kept frame since last time: nothing to judge
        frame_id, ts_ms, jpeg = got
        last_frame = frame_id

        def job(ts: float, img: bytes) -> None:
            indoors = scene_indoors(img)
            if indoors is None:
                return
            st.call("set_scene", ts, not indoors)
            log.info("scene: %s", "indoors" if indoors else "OUTDOORS")

        submit("scene", job, ts_ms, jpeg)

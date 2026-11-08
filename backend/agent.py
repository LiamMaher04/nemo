"""Nemo's agent: Nemotron 3.5 Lightning with tools that read the Spacetime memory.

Text in, text out. ask(question) runs the tool loop and returns the answer plus the tool calls.
NVIDIA's API first (NEMOTRON_*), OpenRouter (OPENROUTER_*) if that call fails. Thinking is off.
"""

import json
import logging
import time
from typing import Any

from openai import OpenAI

from backend import settings
from backend import spacetime_client as st

log = logging.getLogger("nemo.agent")

MAX_STEPS = 5

SYSTEM_PROMPT = """You are Nemo, a small camera clipped to an older person's shirt. Your one job is \
helping them find their everyday things (keys, glasses, phone, TV remote, wallet, their pills \
(a pill bottle), toothbrush) by remembering where you last saw them, and whether the pill bottle \
looks like it was used. Your answer is spoken out loud, so be kind and short: one or two plain sentences, no lists, \
no markdown, no questions back unless you truly can't tell which item they mean.

Honesty comes first. Everything you say must come from your tools in this conversation. You know \
nothing else about this person: not their family or friends, names, ages, health, medicines, \
appointments, plans or past. Never invent, guess or "fill in" a fact, a name, a place or a time, \
even to be friendly. If you're not sure, say so. You are a device, not a person: you have no \
family, feelings or life of your own, and you don't pretend otherwise.

You have a second job: passing a message to their carer with send_carer_alert. Call it whenever \
the person asks you to tell, let know, message or pass something on to anyone (their carer, \
daughter, son, family, "them"), for example "please tell my daughter I'm okay", "let them know I \
can't find my keys", "tell my son I'll ring him later", or says they've fallen, are hurt or need \
help. That is part of your job, so never refuse it: call the tool. Send it even when the message \
mentions one of their things ("let them know I can't find my keys" is a message to send, not a \
question to answer). Never use it on your own initiative, and never for anything else.

If they ask for anything outside these two jobs (a family member's name, the weather, the news, \
the date, medical advice, general chat), don't answer it and don't make something up. Kindly say \
you can only help them find their things, for example: "I'm sorry, I can't help with that. I \
can help you find your things, like your keys or glasses."

About send_carer_alert: The message starts with "Nemo here." and is one short sentence, in \
their own words where you can, about them, for example "Nemo here. They asked me to tell you \
they're okay." or "Nemo here. They say they've fallen and can't get up." Don't add names, \
relationships, places or details they didn't say, and no medical words. It goes to their carer \
(you can't choose who). Then say exactly the tool result's "say" sentence and nothing more: \
never say the carer was told unless the result says requested: true.

Use the tools to look things up before answering. First find_item to work out which item they \
mean: when it finds exactly one item it also tells you where that item was last seen ("where"), \
so you can answer straight away without calling where_is. Use where_is only if find_item didn't \
include "where". Use item_history for questions about whether something was used (for example \
"have I taken my pills?") or when it was last moved around.

When you say where something is, use the "spot" word for word (for example "on the sofa by the \
couch"). If there's a "spot_description" too, add it: it's what the camera saw around the item \
(e.g. "on the desk, between the lamp and the water bottles"). Don't add a room or any other place \
that isn't in the tool results.

look_at_snapshot is slow, so use it only when it changes the answer: confidence under 0.5, two or \
more look-alike candidates, the person asks what the item is next to or for more detail, or they \
ask whether they're indoors or out. Never for a plain "where is it" that already has a spot. \
Whenever they ask how something looks (open or closed, what colour, what's on it or next to it), \
you MUST call look_at_snapshot first and answer from what it says. Never say what a photo shows, \
or that it isn't clear, unless look_at_snapshot told you.

Say times the way a person would: "about 20 minutes ago", "about 2 hours ago", "earlier today". \
Never make up a place, a time or an item. Two different cases, don't mix them up:
- find_item returns found: false: it isn't one of the things you look after, so say you don't \
keep track of that (e.g. "I don't keep track of umbrellas").
- "where" (or where_is) says seen: false: it IS one of your items, you just haven't spotted it \
yet, so say that (e.g. "I haven't seen your keys yet"). Never say you don't keep track of it.
- "where" says seen: true but place_known: false: you did see it, you just couldn't tell where, so \
say that (e.g. "I saw your remote about 20 minutes ago, but I couldn't tell where it was").
If the confidence is low or there are look-alike candidates, say you're not sure.

A "used" event is only a sign, not proof: it means the item went missing from its spot and came \
back. So hedge it, for example "It looks like you took your pills about an hour ago", never "You \
took your pills". Don't give medical advice."""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "find_item",
            "description": "Work out which tracked item the person means, from a name, nickname or "
                           "description. Returns an item_id plus where it was last seen ('where'), "
                           "a list of candidates, or nothing found.",
            "parameters": {
                "type": "object",
                "properties": {"name": {"type": "string", "description": "What the person called it"}},
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "where_is",
            "description": "Where an item was last seen: area, furniture, how long ago, confidence.",
            "parameters": {
                "type": "object",
                "properties": {"item_id": {"type": "string"}},
                "required": ["item_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "look_at_snapshot",
            "description": "Have Nemotron Super VL look at the latest photo of an item and answer a "
                           "question about it (what's around it, which look-alike it is, is the person "
                           "indoors). Slow (a few seconds): only when confidence is low, there are "
                           "look-alike candidates, or the person asks for detail about the spot.",
            "parameters": {
                "type": "object",
                "properties": {
                    "item_id": {"type": "string"},
                    "question": {"type": "string", "description": "What to find out, e.g. 'What is it next to?'"},
                },
                "required": ["item_id", "question"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_carer_alert",
            "description": "Text the person's carer. ONLY when they explicitly ask you to tell or let "
                           "someone know something (their carer, family, 'them'), even if it mentions "
                           "one of their things, or say they've fallen, are hurt or need help. Never "
                           "otherwise.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {"type": "string", "enum": ["asked_to_pass_on", "fallen_hurt_or_needs_help"],
                               "description": "Why: they asked you to pass something on, or they've "
                                              "fallen, are hurt or need help"},
                    "message": {"type": "string",
                                "description": "One short sentence starting 'Nemo here.', in their own "
                                               "words where possible"},
                },
                "required": ["reason", "message"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "item_history",
            "description": "Recent events (placed, used) for an item, newest first, and how often it "
                           "gets used at each hour of the day.",
            "parameters": {
                "type": "object",
                "properties": {"item_id": {"type": "string"}},
                "required": ["item_id"],
            },
        },
    },
]


# ---- Tools ----

def _quote(value: str) -> str:
    """Quote a string for Spacetime SQL."""
    return "'" + value.replace("'", "''") + "'"


def _minutes_ago(ts_ms: float) -> int:
    return max(0, round((time.time() * 1000 - ts_ms) / 60000))


def _norm(text: str) -> str:
    return " ".join(text.lower().replace("'s", "").replace("my ", " ").split())


# items and areas hardly ever change (only when the seed is re-run), so keep them in memory for a
# minute instead of asking Spacetime every question. item_state is always read fresh.
_CACHE_S = 60.0
_cache: dict[str, tuple[float, Any]] = {}


def _cached(key: str, query: str) -> list[dict[str, Any]]:
    hit = _cache.get(key)
    if hit and time.monotonic() - hit[0] < _CACHE_S:
        return hit[1]
    rows = st.sql(query)
    _cache[key] = (time.monotonic(), rows)
    return rows


def _items() -> list[dict[str, Any]]:
    return _cached("items", "SELECT * FROM items")


def _area_name(area_id: str) -> str:
    for a in _cached("areas", "SELECT * FROM areas"):
        if a["area_id"] == area_id:
            return a["name"]
    return area_id.replace("_", " ")


def find_item(name: str) -> dict[str, Any]:
    wanted = _norm(name)
    items = _items()
    exact, partial = [], []
    for it in items:
        names = [it["item_id"].replace("_", " "), it["name"], *it["aliases"]]
        names = [_norm(n) for n in names]
        if wanted in names:
            exact.append(it)
            continue
        attributes = _norm(it["attributes"])
        if any(wanted in n or n in wanted for n in names) or (len(wanted) > 3 and wanted in attributes):
            partial.append(it)
    matches = exact or partial
    if len(matches) == 1:
        # Include where it was last seen, so the agent can answer without a separate where_is call
        # (one fewer model round trip, about 1.5 s quicker).
        item_id = matches[0]["item_id"]
        return {"item_id": item_id, "name": matches[0]["name"], "where": where_is(item_id)}
    if matches:
        return {"candidates": [{"item_id": m["item_id"], "name": m["name"]} for m in matches]}
    return {"found": False, "tracked_items": [it["name"] for it in items]}


def _spot_phrase(furniture: str, area: str) -> str:
    """Say a spot the way a person would: "on the sofa by the couch", or "on the desk"."""
    if not area and not furniture:
        return "somewhere I couldn't place"
    if not area:  # area_id is "" until DINOv2 area matching lands
        return f"on the {furniture}"
    if not furniture:
        return f"by the {area}"
    if furniture.lower() == area.lower():
        return f"on the {furniture}"
    by = area if area[-1:].isdigit() else f"the {area}"  # "by bed 1", "by the couch"
    return f"on the {furniture} by {by}"


def where_is(item_id: str) -> dict[str, Any]:
    rows = st.sql(f"SELECT * FROM item_state WHERE item_id = {_quote(item_id)}")
    if not rows:
        # A tracked item with no last-seen row yet: Nemo looks after it but hasn't spotted it.
        return {"item_id": item_id, "tracked": True, "seen": False,
                "note": "This is one of the tracked items; Nemo just hasn't seen it yet."}
    s = rows[0]
    area = _area_name(s["area_id"]) if s["area_id"] else ""
    furniture = s["furniture"]
    candidates = json.loads(s["candidates_json"]) if s["candidates_json"] else []
    if not area and not furniture:
        # Seen, but with no furniture or area recognised: say when, not where.
        return {
            "item_id": item_id,
            "seen": True,
            "place_known": False,
            "minutes_ago": _minutes_ago(s["last_seen_ts_ms"]),
            "note": "Nemo saw it but couldn't tell where it was.",
        }
    return {
        "item_id": item_id,
        "seen": True,
        "spot": _spot_phrase(furniture, area),
        "area": area,
        "furniture": furniture,
        "spot_description": s["spot_description"],
        "minutes_ago": _minutes_ago(s["last_seen_ts_ms"]),
        "confidence": round(s["confidence"], 2),
        "candidates": candidates,
    }


def item_history(item_id: str) -> dict[str, Any]:
    events = st.sql(f"SELECT * FROM events WHERE item_id = {_quote(item_id)}")
    events.sort(key=lambda e: e["ts_ms"], reverse=True)
    routines = st.sql(f"SELECT * FROM routines WHERE item_id = {_quote(item_id)}")
    return {
        "item_id": item_id,
        "events": [
            {
                "type": e["type"],
                "minutes_ago": _minutes_ago(e["ts_ms"]),
                "to": json.loads(e["to_json"]) if e["to_json"] else None,
            }
            for e in events[:10]
        ],
        "uses_by_hour": {str(r["hour"]): r["use_count"] for r in sorted(routines, key=lambda r: r["hour"])},
    }


def look_at_snapshot(item_id: str, question: str = "Where exactly is it, and what is it next to?") -> dict[str, Any]:
    """Super VL looks at the newest saved frame that shows this item. Capped at a few seconds."""
    from backend import settings as cfg
    from backend import vl

    if not cfg.SUPER_VL:
        return {"available": False, "reason": "Super VL is switched off"}
    rows = st.sql(f"SELECT * FROM sightings WHERE item_id = {_quote(item_id)}")
    rows.sort(key=lambda r: r["ts_ms"], reverse=True)
    names = {it["item_id"]: it["name"] for it in _items()}
    name = names.get(item_id, item_id.replace("_", " "))
    for r in rows[:5]:  # the newest sighting whose frame is still on disk
        path = cfg.FRAMES_DIR / f"{int(r['frame_id'])}.jpg"
        if path.exists():
            try:
                answer = vl.answer_about(path.read_bytes(), r["bbox_json"], name, question)
            except Exception as exc:
                return {"available": False, "reason": f"Super VL didn't answer in time: {exc}"}
            return {"item_id": item_id, "minutes_ago": _minutes_ago(r["ts_ms"]), "answer": answer}
    # No frame left on disk: fall back to the thumbnail Spacetime kept (small, but something).
    state = st.sql(f"SELECT * FROM item_state WHERE item_id = {_quote(item_id)}")
    if state and state[0]["thumb_b64"]:
        import base64
        try:
            answer = vl.answer_about(base64.b64decode(state[0]["thumb_b64"]), None, name, question)
        except Exception as exc:
            return {"available": False, "reason": f"Super VL didn't answer in time: {exc}"}
        return {"item_id": item_id, "minutes_ago": _minutes_ago(state[0]["last_seen_ts_ms"]),
                "answer": answer, "note": "from a small thumbnail, so less detail"}
    return {"available": False, "reason": "no photo of that item is kept"}


def send_carer_alert(reason: str, message: str) -> dict[str, Any]:
    """Ask Spacetime to record a carer alert (type agent_request). Never calls Photon itself: the
    backend's sender loop texts it, so CARER_ALERTS still decides whether anything is sent.
    Spacetime allows one agent_request every 10 minutes."""
    text = " ".join(str(message).split())[:300]
    if not text:
        return {"requested": False, "error": "empty message"}
    if not text.lower().startswith("nemo here"):
        text = "Nemo here. " + text
    asked_at = time.time() * 1000
    st.call("request_carer_alert", "agent_request", text)
    # Spacetime decides (one every 10 minutes) and writes nothing if it's too soon: read back.
    rows = [r for r in st.sql("SELECT * FROM alerts WHERE type = 'agent_request'")]
    newest = max(rows, key=lambda r: r["ts_ms"], default=None)
    if newest and newest["message"] == text and newest["ts_ms"] >= asked_at - 30_000:
        log.info("send_carer_alert (%s) requested: %r", reason, text)
        return {"requested": True, "reason": reason, "message": text,
                "say": "Okay, I've let your carer know."}
    minutes = round((asked_at - newest["ts_ms"]) / 60000) if newest else None
    log.info("send_carer_alert (%s) too soon (last one %s min ago): %r", reason, minutes, text)
    return {"requested": False, "too_soon": True, "minutes_since_last": minutes,
            "note": "NOT sent: their carer was already sent a message in the last 10 minutes.",
            "say": "I sent your carer a message a few minutes ago, so I can't send another one just yet."}


TOOL_FUNCTIONS = {"find_item": find_item, "where_is": where_is, "item_history": item_history,
                  "look_at_snapshot": look_at_snapshot, "send_carer_alert": send_carer_alert}


def _run_tool(name: str, raw_args: str) -> tuple[dict[str, Any], Any]:
    try:
        args = json.loads(raw_args or "{}")
    except json.JSONDecodeError:
        return {}, {"error": "arguments were not valid JSON"}
    fn = TOOL_FUNCTIONS.get(name)
    if not fn:
        return args, {"error": f"unknown tool {name}"}
    try:
        return args, fn(**args)
    except Exception as exc:  # report back to the model rather than crash the answer
        log.exception("tool %s failed", name)
        return args, {"error": str(exc)}


# ---- Model calls ----

def _providers() -> list[tuple[str, OpenAI, str, dict[str, Any]]]:
    providers = []
    if settings.NEMOTRON_API_KEY:
        providers.append((
            "nvidia",
            OpenAI(base_url=settings.NEMOTRON_BASE_URL, api_key=settings.NEMOTRON_API_KEY),
            settings.NEMOTRON_AGENT_MODEL,
            {"chat_template_kwargs": {"enable_thinking": False}},
        ))
    if settings.OPENROUTER_API_KEY:
        providers.append((
            "openrouter",
            OpenAI(base_url=settings.OPENROUTER_BASE_URL, api_key=settings.OPENROUTER_API_KEY),
            settings.OPENROUTER_MODEL,
            {"reasoning": {"enabled": False}},
        ))
    return providers


def _chat(messages: list[dict[str, Any]], final: bool) -> tuple[Any, str]:
    """One model call. NVIDIA first, OpenRouter if it fails. final=True stops further tool calls."""
    providers = _providers()
    if not providers:
        raise RuntimeError("No model key set: add NEMOTRON_API_KEY (or OPENROUTER_API_KEY) to .env")
    last_error: Exception | None = None
    for name, client, model, extra in providers:
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=messages,
                tools=TOOLS,
                tool_choice="none" if final else "auto",
                temperature=0.2,
                max_tokens=200,  # spoken answers are one or two sentences
                extra_body=extra,
                timeout=30,
            )
            return resp.choices[0].message, name
        except Exception as exc:
            log.warning("%s call failed: %s", name, exc)
            last_error = exc
    raise RuntimeError(f"All model providers failed: {last_error}")


def _items_named_in(question: str) -> list[dict[str, Any]]:
    """Tracked items whose name, id or an alias appears as whole words in the question."""
    q = " " + " ".join("".join(c if c.isalnum() else " " for c in question.lower()).split()) + " "
    found = []
    for it in _items():
        names = {it["item_id"].replace("_", " "), it["name"].lower(), *(a.lower() for a in it["aliases"])}
        if any(f" {n} " in q for n in names if n):
            found.append(it)
    return found


# Questions asking Nemo to pass something on ("let them know I can't find my keys" is a message for
# the carer, not a question about the keys): no prefetch, and a one-line hint so the agent sees it.
PASS_ON_WORDS = (" tell ", " let them know", " let her know", " let him know", " let my ", " message ",
                 " pass on ", " ring my ", " call my ")
PASS_ON_HINT = ("This sounds like a message for their carer: use send_carer_alert, then say its 'say' "
                "sentence.")


def _asks_to_pass_on(question: str) -> bool:
    q = " " + " ".join("".join(c if c.isalnum() or c == "'" else " " for c in question.lower()).split()) + " "
    q = q.replace(" tell me ", " ")  # "can you tell me where my keys are" is a question for Nemo
    return any(w in q for w in PASS_ON_WORDS)


def _prefetch(question: str) -> list[tuple[str, dict[str, Any], Any]]:
    """If the question names exactly one tracked item, look it up before the first model call.

    Returns (tool name, args, result) tuples to put in the conversation as if the agent had called
    them, so a plain "where's my X?" is answered in ONE Nemotron call instead of two (~1.5 s
    quicker). The agent keeps all its tools for anything else. For important items (the pills)
    item_history is fetched too, for "have I taken my pills?".
    """
    if _asks_to_pass_on(question):
        return []  # a message for their carer, not a "where is it": let the agent use send_carer_alert
    named = _items_named_in(question)
    if len(named) != 1:
        return []
    item = named[0]
    calls = [("find_item", {"name": item["name"]}, find_item(item["name"]))]
    if item["importance"] >= 3:
        calls.append(("item_history", {"item_id": item["item_id"]}, item_history(item["item_id"])))
    return calls


def ask(question: str) -> dict[str, Any]:
    """Answer a question with up to MAX_STEPS model calls. Returns answer, tool_calls, timings."""
    started = time.perf_counter()
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]
    if _asks_to_pass_on(question):
        messages.insert(1, {"role": "system", "content": PASS_ON_HINT})
    tool_calls: list[dict[str, Any]] = []
    answer = ""
    provider = ""

    # Look the item up before asking the model, when the question clearly names one.
    try:
        prefetched = _prefetch(question)
    except Exception as exc:  # never let the shortcut break an answer: fall back to the normal loop
        log.warning("prefetch failed, the agent will look it up itself: %s", exc)
        prefetched = []
    if prefetched:
        ids = [f"prefetch_{i}" for i in range(len(prefetched))]
        messages.append({
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {"id": cid, "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}
                for cid, (name, args, _) in zip(ids, prefetched)
            ],
        })
        for cid, (name, args, result) in zip(ids, prefetched):
            messages.append({"role": "tool", "tool_call_id": cid, "content": json.dumps(result)})
            tool_calls.append({"name": name, "args": args, "result": result, "ms": 0, "prefetched": True})
            log.info("prefetched %s(%s) -> %s", name, json.dumps(args), json.dumps(result))

    for step in range(MAX_STEPS):
        msg, provider = _chat(messages, final=step == MAX_STEPS - 1)
        if not msg.tool_calls:
            answer = (msg.content or "").strip()  # only content is spoken, never reasoning
            break
        messages.append({
            "role": "assistant",
            "content": msg.content or "",
            "tool_calls": [
                {"id": tc.id, "type": "function",
                 "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in msg.tool_calls
            ],
        })
        for tc in msg.tool_calls:
            t0 = time.perf_counter()
            args, result = _run_tool(tc.function.name, tc.function.arguments)
            ms = round((time.perf_counter() - t0) * 1000)
            log.info("tool %s(%s) -> %s [%d ms]", tc.function.name, json.dumps(args), json.dumps(result), ms)
            tool_calls.append({"name": tc.function.name, "args": args, "result": result, "ms": ms})
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": json.dumps(result)})

    if not answer:
        answer = "Sorry, I'm not sure right now."
    total_ms = round((time.perf_counter() - started) * 1000)
    log.info("ask %r -> %r via %s in %d ms (%d tool calls)", question, answer, provider, total_ms, len(tool_calls))
    return {"answer": answer, "tool_calls": tool_calls, "provider": provider, "total_ms": total_ms}

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
helping them find their everyday things (keys, glasses, phone, TV remote, wallet, pill box, \
toothbrush) by remembering where you last saw them, and whether the pill box looks like it was \
used. Your answer is spoken out loud, so be kind and short: one or two plain sentences, no lists, \
no markdown, no questions back unless you truly can't tell which item they mean.

Honesty comes first. Everything you say must come from your tools in this conversation. You know \
nothing else about this person: not their family or friends, names, ages, health, medicines, \
appointments, plans or past. Never invent, guess or "fill in" a fact, a name, a place or a time, \
even to be friendly. If you're not sure, say so. You are a device, not a person: you have no \
family, feelings or life of your own, and you don't pretend otherwise.

If they ask for anything outside your job (a family member's name, the weather, the news, the \
date, medical advice, general chat), don't answer it and don't make something up. Kindly say \
you can only help them find their things, for example: "I'm sorry, I can't help with that. I \
can help you find your things, like your keys or glasses."

Use the tools to look things up before answering. First find_item to work out which item they \
mean: when it finds exactly one item it also tells you where that item was last seen ("where"), \
so you can answer straight away without calling where_is. Use where_is only if find_item didn't \
include "where". Use item_history for questions about whether something was used (for example \
"have I taken my pills?") or when it was last moved around.

When you say where something is, use the "spot" word for word (for example "on the sofa by the \
couch"). Don't add a room or any other place that isn't in the tool results.

Say times the way a person would: "about 20 minutes ago", "about 2 hours ago", "earlier today". \
Never make up a place, a time or an item. Two different cases, don't mix them up:
- find_item returns found: false: it isn't one of the things you look after, so say you don't \
keep track of that (e.g. "I don't keep track of umbrellas").
- "where" (or where_is) says seen: false: it IS one of your items, you just haven't spotted it \
yet, so say that (e.g. "I haven't seen your keys yet"). Never say you don't keep track of it.
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


def find_item(name: str) -> dict[str, Any]:
    wanted = _norm(name)
    items = st.sql("SELECT * FROM items")
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
    area_rows = st.sql(f"SELECT * FROM areas WHERE area_id = {_quote(s['area_id'])}")
    area = area_rows[0]["name"] if area_rows else s["area_id"].replace("_", " ")
    furniture = s["furniture"]
    candidates = json.loads(s["candidates_json"]) if s["candidates_json"] else []
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


TOOL_FUNCTIONS = {"find_item": find_item, "where_is": where_is, "item_history": item_history}


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
                max_tokens=400,
                extra_body=extra,
                timeout=30,
            )
            return resp.choices[0].message, name
        except Exception as exc:
            log.warning("%s call failed: %s", name, exc)
            last_error = exc
    raise RuntimeError(f"All model providers failed: {last_error}")


def ask(question: str) -> dict[str, Any]:
    """Answer a question with up to MAX_STEPS model calls. Returns answer, tool_calls, timings."""
    started = time.perf_counter()
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]
    tool_calls: list[dict[str, Any]] = []
    answer = ""
    provider = ""

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

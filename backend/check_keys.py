"""Check every service connects. Never prints keys. Run from repo root: python -m backend.check_keys"""
from __future__ import annotations

from openai import OpenAI

from backend.app import config, spacetime


def ok(name: str, fn) -> None:
    try:
        print(f"[ OK ] {name}: {fn()}")
    except Exception as e:
        print(f"[FAIL] {name}: {str(e)[:200]}")


def nvidia() -> str:
    if not config.NEMOTRON_API_KEY:
        raise RuntimeError("NEMOTRON_API_KEY is empty")
    c = OpenAI(base_url=config.NEMOTRON_BASE_URL, api_key=config.NEMOTRON_API_KEY)
    r = c.chat.completions.create(
        model=config.NEMOTRON_AGENT_MODEL, max_tokens=20,
        messages=[{"role": "user", "content": "Reply with the single word: ready"}],
        extra_body={"chat_template_kwargs": {"enable_thinking": False}})
    return f"{config.NEMOTRON_AGENT_MODEL} says {r.choices[0].message.content!r}"


def openrouter() -> str:
    if not config.OPENROUTER_API_KEY:
        return "skipped (no key)"
    c = OpenAI(base_url=config.OPENROUTER_BASE_URL, api_key=config.OPENROUTER_API_KEY)
    r = c.chat.completions.create(model=config.OPENROUTER_MODEL, max_tokens=20,
                                  messages=[{"role": "user", "content": "Reply: ready"}])
    return f"{config.OPENROUTER_MODEL} says {r.choices[0].message.content!r}"


def spacetime_db() -> str:
    rows = spacetime.sql("SELECT * FROM items")
    return f"{config.SPACETIME_DB} reachable, {len(rows)} items"


if __name__ == "__main__":
    ok("NVIDIA Nemotron", nvidia)
    ok("OpenRouter fallback", openrouter)
    ok("SpacetimeDB", spacetime_db)

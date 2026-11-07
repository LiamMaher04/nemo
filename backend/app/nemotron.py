"""Nemotron client (OpenAI-compatible). NVIDIA API first, OpenRouter fallback."""
from __future__ import annotations

import logging
from typing import Any

from openai import OpenAI

from . import config

log = logging.getLogger("nemo.nemotron")


def _clients() -> list[tuple[OpenAI, str]]:
    out = []
    if config.NEMOTRON_API_KEY:
        out.append((OpenAI(base_url=config.NEMOTRON_BASE_URL, api_key=config.NEMOTRON_API_KEY),
                    config.NEMOTRON_AGENT_MODEL))
    if config.OPENROUTER_API_KEY and config.OPENROUTER_MODEL:
        out.append((OpenAI(base_url=config.OPENROUTER_BASE_URL, api_key=config.OPENROUTER_API_KEY),
                    config.OPENROUTER_MODEL))
    return out


def chat(messages: list[dict[str, Any]], thinking: bool | None = None, max_tokens: int = 400,
         tools: list[dict[str, Any]] | None = None) -> Any:
    """Return the assistant message. Thinking is off by default (keeps spoken answers quick)."""
    think = config.NEMOTRON_THINKING if thinking is None else thinking
    last_err: Exception | None = None
    for client, model in _clients():
        try:
            kwargs: dict[str, Any] = dict(model=model, messages=messages, max_tokens=max_tokens,
                                          temperature=0.3)
            if tools:
                kwargs["tools"] = tools
            if "nvidia.com" in str(client.base_url):
                kwargs["extra_body"] = {"chat_template_kwargs": {"enable_thinking": think}}
            r = client.chat.completions.create(**kwargs)
            return r.choices[0].message
        except Exception as e:  # fall through to the next provider
            log.warning("Nemotron call failed on %s: %s", client.base_url, e)
            last_err = e
    raise RuntimeError(f"No Nemotron provider worked: {last_err}")


def say(messages: list[dict[str, Any]], **kw: Any) -> str:
    """Just the spoken text (never the reasoning)."""
    return (chat(messages, **kw).content or "").strip()

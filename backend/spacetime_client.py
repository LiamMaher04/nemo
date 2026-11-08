"""Talk to the Nemo SpacetimeDB database over HTTP.

- call(reducer, *args): POST {SPACETIME_URL}/v1/database/{SPACETIME_DB}/call/{reducer},
  body is a JSON array of the reducer's arguments in order.
- sql(query): POST {SPACETIME_URL}/v1/database/{SPACETIME_DB}/sql, body is the SQL text.
  Returns the rows of the last statement as a list of dicts.

Auth: if SPACETIME_TOKEN is set it's sent as "Authorization: Bearer <token>". Without it,
SpacetimeDB gives each request a new anonymous identity, which can still call reducers and read
public tables.
"""

import logging
import time
from typing import Any

import httpx

from backend import settings

log = logging.getLogger("nemo.spacetime")

_client = httpx.Client(timeout=10.0)


def _url(path: str) -> str:
    return f"{settings.SPACETIME_URL.rstrip('/')}/v1/database/{settings.SPACETIME_DB}/{path}"


def _headers(content_type: str) -> dict[str, str]:
    headers = {"Content-Type": content_type}
    if settings.SPACETIME_TOKEN:
        headers["Authorization"] = f"Bearer {settings.SPACETIME_TOKEN}"
    return headers


def call(reducer: str, *args: Any) -> None:
    """Call a reducer. Raises on any non-2xx reply (the reply text says why)."""
    started = time.perf_counter()
    r = _client.post(_url(f"call/{reducer}"), json=list(args), headers=_headers("application/json"))
    if r.status_code >= 300:
        raise RuntimeError(f"{reducer} failed ({r.status_code}): {r.text}")
    log.info("called %s in %.0f ms", reducer, (time.perf_counter() - started) * 1000)


def sql(query: str) -> list[dict[str, Any]]:
    """Run SQL and return the last statement's rows as dicts keyed by column name."""
    r = _client.post(_url("sql"), content=query.encode(), headers=_headers("text/plain"))
    if r.status_code >= 300:
        raise RuntimeError(f"sql failed ({r.status_code}): {r.text}")
    results = r.json()
    if not results:
        return []
    last = results[-1]
    names = [el["name"]["some"] if isinstance(el.get("name"), dict) else el.get("name")
             for el in last["schema"]["elements"]]
    return [dict(zip(names, row)) for row in last["rows"]]

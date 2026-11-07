"""Tiny SpacetimeDB HTTP client: call reducers and run SQL. No Python SDK exists, plain HTTP works.

POST {url}/v1/database/{db}/call/{reducer}   body = JSON array of the reducer's args, in order
POST {url}/v1/database/{db}/sql              body = SQL text

If SPACETIME_TOKEN is empty we ask the server for a fresh identity token once (POST /v1/identity)
and reuse it. Check spacetimedb.com/docs/http if auth or response shapes have changed.
"""
from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from . import config

log = logging.getLogger("nemo.spacetime")
_token: str | None = config.SPACETIME_TOKEN or None
_client = httpx.Client(timeout=10)


def _headers() -> dict[str, str]:
    global _token
    if not _token:
        r = _client.post(f"{config.SPACETIME_URL}/v1/identity")
        r.raise_for_status()
        _token = r.json()["token"]
        log.info("got a Spacetime identity token (add SPACETIME_TOKEN to .env to reuse it)")
    return {"Authorization": f"Bearer {_token}"}


def call(reducer: str, *args: Any) -> None:
    url = f"{config.SPACETIME_URL}/v1/database/{config.SPACETIME_DB}/call/{reducer}"
    r = _client.post(url, headers={**_headers(), "Content-Type": "application/json"},
                     content=json.dumps(list(args)))
    if r.status_code >= 400:
        raise RuntimeError(f"{reducer} failed {r.status_code}: {r.text[:300]}")


def sql(query: str) -> list[dict[str, Any]]:
    """Run SQL and return rows as dicts (column names from the response schema)."""
    url = f"{config.SPACETIME_URL}/v1/database/{config.SPACETIME_DB}/sql"
    r = _client.post(url, headers=_headers(), content=query)
    if r.status_code >= 400:
        raise RuntimeError(f"sql failed {r.status_code}: {r.text[:300]}")
    out: list[dict[str, Any]] = []
    for result in r.json():
        cols = []
        for el in result.get("schema", {}).get("elements", []):
            name = el.get("name")
            if isinstance(name, dict):  # {"some": "col"}
                name = name.get("some")
            cols.append(name)
        for row in result.get("rows", []):
            out.append(dict(zip(cols, row)))
    return out


def add_sighting(s: dict[str, Any]) -> None:
    """Argument order must match add_sighting in spacetime/nemo_module.ts and docs/interfaces.md."""
    call(
        "add_sighting",
        float(s["ts_ms"]), float(s.get("frame_id", 0)), int(s.get("track_id", -1)),
        s.get("label", ""), float(s.get("det_conf", 0)), s.get("item_id", ""),
        json.dumps(s.get("candidates", [])), float(s.get("match_margin", 0)),
        s.get("room_id", ""), float(s.get("room_conf", 0)),
        s.get("anchor_id", ""), s.get("relation", ""),
        json.dumps(s.get("bbox", [0, 0, 0, 0])), bool(s.get("in_hand", False)),
        s.get("thumb_b64", ""),
    )


def where_is(item_id: str) -> dict[str, Any] | None:
    safe = item_id.replace("'", "''")
    rows = sql(f"SELECT * FROM item_state WHERE item_id = '{safe}'")
    return rows[0] if rows else None

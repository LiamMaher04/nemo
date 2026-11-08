"""Ask the agent a few questions against some seeded placements.

Run from the repo root:  backend\\.venv\\Scripts\\python.exe -m backend.test_agent
Needs NEMOTRON_API_KEY (or OPENROUTER_API_KEY) in .env.
WARNING: calls reset_memory first. Items and areas are kept.
"""

import json
import time

from fastapi.testclient import TestClient

from backend import spacetime_client as st
from backend import test_memory as tm
from backend.main import app

QUESTIONS = [
    "where's my remote?",
    "where are my specs?",
    "have I taken my pills?",
    "where's my umbrella?",
]


def seed_placements() -> None:
    st.call("reset_memory")
    now_ms = time.time() * 1000

    # Glasses on bed 1's bedside table, about 2 hours ago.
    tm.clock_ms = now_ms - 2 * 3600 * 1000
    tm.sight("reading_glasses", "bed_1", "bedside table", label="eyeglasses")
    tm.sight("reading_glasses", "bed_1", "bedside table", label="eyeglasses")

    # Pill box on the desk; missing in a sharp desk frame; back on the desk. About 1 hour ago.
    tm.clock_ms = now_ms - 60 * 60 * 1000
    tm.sight("pill_box", "desk", "desk")
    tm.sight("pill_box", "desk", "desk")
    tm.frame("desk", ["desk"], [], tm.SHARP)
    tm.sight("pill_box", "desk", "desk")

    # Remote on the couch, about 20 minutes ago.
    tm.clock_ms = now_ms - 20 * 60 * 1000
    tm.sight("tv_remote", "couch", "sofa")
    tm.sight("tv_remote", "couch", "sofa")

    for s in st.sql("SELECT * FROM item_state"):
        mins = round((now_ms - s["last_seen_ts_ms"]) / 60000)
        print(f"  seeded {s['item_id']:<16} {s['area_id']}/{s['furniture']}, {mins} min ago")
    for e in st.sql("SELECT * FROM events"):
        print(f"  event  {e['item_id']:<16} {e['type']}")


def main() -> None:
    print("Seeding placements:")
    seed_placements()

    client = TestClient(app)
    for q in QUESTIONS:
        started = time.perf_counter()
        r = client.post("/ask_text", json={"question": q})
        secs = time.perf_counter() - started
        print(f"\nQ: {q}")
        if r.status_code != 200:
            print(f"  HTTP {r.status_code}: {r.text}")
            continue
        body = r.json()
        print(f"A: {body['answer']}")
        for tc in body["tool_calls"]:
            print(f"   tool {tc['name']}({json.dumps(tc['args'])}) -> {json.dumps(tc['result'])}")
        print(f"   ({len(body['tool_calls'])} tool calls, {secs:.1f} s)")


if __name__ == "__main__":
    main()

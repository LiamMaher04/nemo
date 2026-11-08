"""Exercise the memory rules in the Spacetime module with fake reports from vision.

Run from the repo root:  backend\\.venv\\Scripts\\python.exe -m backend.test_memory
WARNING: calls reset_memory first, which clears sightings, item_state, events, routines, alerts and
tracking. Items and areas are kept.
"""

import json
import time

from backend import spacetime_client as st

ITEM_LABELS = {
    "tv_remote": "tv remote control",
    "pill_box": "pill organizer box",
}

SHARP = 150.0
BLURRY = 40.0

clock_ms = time.time() * 1000  # fake clock: each report is one second after the last
frame_id = 0


def _tick() -> tuple[float, float]:
    global clock_ms, frame_id
    clock_ms += 1000
    frame_id += 1
    return clock_ms, float(frame_id)


def sight(item_id: str, area_id: str, furniture: str, label: str | None = None) -> None:
    """One add_sighting: item_id "" means ambiguous (two look-alikes, tiny margin)."""
    ts, fid = _tick()
    st.call(
        "add_sighting",
        ts,
        fid,
        area_id,
        0.9,
        label or ITEM_LABELS.get(item_id, "unknown"),
        0.85,
        item_id,
        json.dumps([[item_id, 0.9]] if item_id else [["keys", 0.81], ["wallet", 0.79]]),
        0.3 if item_id else 0.02,
        furniture,
        json.dumps([0.5, 0.5]) if furniture else "",
        SHARP,
        json.dumps([600, 460, 80, 40]),
        "",
    )


def frame(area_id: str, furniture_in_view: list[str], items_seen: list[str], sharpness: float) -> None:
    """One add_frame: what furniture was in view and which items were seen in that kept frame."""
    ts, fid = _tick()
    st.call(
        "add_frame",
        ts,
        fid,
        area_id,
        0.9,
        json.dumps(furniture_in_view),
        json.dumps(items_seen),
        sharpness,
    )


seen_events = 0


def show(title: str) -> None:
    global seen_events
    print(f"\n=== {title}")
    for s in st.sql("SELECT * FROM item_state"):
        print(f"  item_state {s['item_id']:<10} state={s['state']:<7} area={s['area_id']:<6} "
              f"furniture={s['furniture']:<5} seen_at={s['last_seen_ts_ms']:.0f}")
    events = sorted(st.sql("SELECT * FROM events"), key=lambda e: e["id"])
    new = events[seen_events:]
    seen_events = len(events)
    if not new:
        print("  new events: none")
    for e in new:
        print(f"  new event  #{e['id']} {e['item_id']:<10} {e['type']:<6} from={e['from_json'] or '-'} "
              f"to={e['to_json']}")


def show_routines() -> None:
    rows = st.sql("SELECT * FROM routines")
    if not rows:
        print("  routines: none")
    for r in rows:
        print(f"  routines   {r['item_id']} hour={r['hour']} use_count={r['use_count']}")


def main() -> None:
    st.call("reset_memory")
    print("reset_memory: done")

    # (a) Remote seen twice on the couch.
    sight("tv_remote", "couch", "sofa")
    sight("tv_remote", "couch", "sofa")
    show("(a) remote seen twice on the couch -> placed at couch")

    # (b) One stray sighting on the desk: not enough to change anything.
    sight("tv_remote", "desk", "desk")
    show("(b) one stray sighting on the desk -> still at couch, no event")

    # (c) Seen twice on the desk.
    sight("tv_remote", "desk", "desk")
    show("(c) remote seen twice on the desk -> placed at desk, one placed event")

    # (d) Pill box on the desk; a sharp desk frame without it; seen back on the desk.
    sight("pill_box", "desk", "desk")
    sight("pill_box", "desk", "desk")
    frame("desk", ["desk"], ["tv_remote"], SHARP)
    sight("pill_box", "desk", "desk")
    show("(d) pill box missing in a sharp frame, then back on the desk -> used")
    show_routines()

    # (e) Same again, but the frame without it is blurry, so it isn't a clear view.
    frame("desk", ["desk"], [], BLURRY)
    sight("pill_box", "desk", "desk")
    show("(e) same with a blurry frame -> no used")
    show_routines()

    # (f) Ambiguous sighting: item_id "".
    before = (st.sql("SELECT * FROM item_state"), st.sql("SELECT * FROM events"))
    sight("", "desk", "desk", label="house keys on keyring")
    after = (st.sql("SELECT * FROM item_state"), st.sql("SELECT * FROM events"))
    show("(f) ambiguous sighting -> nothing changes")
    print(f"  item_state and events unchanged: {before == after}")
    print(f"  sightings stored: {len(st.sql('SELECT * FROM sightings'))}")


if __name__ == "__main__":
    main()

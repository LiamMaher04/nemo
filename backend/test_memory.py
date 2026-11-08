"""Exercise the placement rules in the Spacetime add_sighting reducer with fake sightings.

Run from the repo root:  backend\\.venv\\Scripts\\python.exe -m backend.test_memory
WARNING: calls reset_memory first, which clears sightings, item_state, events, routines, alerts.
Items and areas are kept.
"""

import json
import time

from backend import spacetime_client as st

ITEM_LABELS = {
    "tv_remote": "tv remote control",
    "pill_box": "pill organizer box",
    "keys": "house keys on keyring",
    "phone": "cell phone",
}

clock_ms = time.time() * 1000  # fake clock: each sighting is one second after the last
frame_id = 0


def sight(item_id: str, area_id: str, furniture: str, mwb: float, centre: tuple[int, int] = (640, 480),
          label: str | None = None) -> None:
    """Send one sighting, one second after the previous one."""
    global clock_ms, frame_id
    clock_ms += 1000
    frame_id += 1
    w, h = 80, 40
    bbox = [centre[0] - w // 2, centre[1] - h // 2, w, h]
    st.call(
        "add_sighting",
        clock_ms,
        float(frame_id),
        area_id,
        0.9,
        label or ITEM_LABELS.get(item_id, "unknown"),
        0.85,
        item_id,
        json.dumps([[item_id, 0.9]] if item_id else [["keys", 0.81], ["wallet", 0.79]]),
        0.3 if item_id else 0.02,
        furniture,
        json.dumps([0.5, 0.5]) if furniture else "",
        mwb,
        150.0,
        json.dumps(bbox),
        "",
    )


def resting(item_id: str, area_id: str, furniture: str, frames: int = 3, step_px: int = 0) -> None:
    """Item stays with the room. step_px moves its bbox centre each frame (the wearer walking)."""
    for i in range(frames):
        sight(item_id, area_id, furniture, 0.95, centre=(640 + i * step_px, 480))


def carried(item_id: str, area_id: str, seconds: int = 3) -> None:
    """Item fixed to the camera while the background moves, one sighting a second."""
    for _ in range(seconds + 1):
        sight(item_id, area_id, "", 0.1)


seen_events = 0


def show(title: str) -> None:
    global seen_events
    print(f"\n=== {title}")
    for s in st.sql("SELECT * FROM item_state"):
        print(f"  item_state {s['item_id']:<10} state={s['state']:<8} area={s['area_id'] or '-':<11} "
              f"furniture={s['furniture'] or '-':<6} placed_at={s['last_placed_ts_ms']:.0f} "
              f"seen_at={s['last_seen_ts_ms']:.0f}")
    events = sorted(st.sql("SELECT * FROM events"), key=lambda e: e["id"])
    new = events[seen_events:]
    seen_events = len(events)
    if not new:
        print("  new events: none")
    for e in new:
        print(f"  new event  #{e['id']} {e['item_id']:<10} {e['type']:<9} from={e['from_json'] or '-'} "
              f"to={e['to_json']}")


def main() -> None:
    st.call("reset_memory")
    print("reset_memory: done")

    # (a) Remote put down on the couch: three resting frames on the sofa.
    resting("tv_remote", "couch", "sofa")
    show("(a) remote put down on the couch -> placed at couch")

    # (b) Remote picked up, carried for 3 s, put down on the desk.
    carried("tv_remote", "couch", seconds=3)
    show("(b1) remote carried for 3 s -> carried, one picked_up event")
    resting("tv_remote", "desk", "desk")
    show("(b2) remote put down on the desk -> placed at desk")

    # (c) Pill box on the desk, carried, put back on the desk.
    resting("pill_box", "desk", "desk")
    show("(c1) pill box seen on the desk -> placed")
    carried("pill_box", "desk", seconds=3)
    resting("pill_box", "desk", "desk")
    show("(c2) pill box carried and put back -> picked_up, placed, used")
    for r in st.sql("SELECT * FROM routines"):
        print(f"  routines   {r['item_id']} hour={r['hour']} use_count={r['use_count']}")

    # (d) Keys on bed 1, then turn up in the closet (no furniture, camera moving) without being carried.
    resting("keys", "bed_1", "bed")
    resting("keys", "closet", "", frames=3, step_px=40)
    show("(d) keys turn up in the closet without being carried -> moved")

    # (e) Ambiguous sighting: item_id "" (keys or wallet, tiny margin).
    before = (st.sql("SELECT * FROM item_state"), st.sql("SELECT * FROM events"))
    sight("", "closet", "", 0.95, label="house keys on keyring")
    after = (st.sql("SELECT * FROM item_state"), st.sql("SELECT * FROM events"))
    show("(e) ambiguous sighting")
    print(f"  item_state and events unchanged: {before == after}")
    print(f"  sightings stored: {len(st.sql('SELECT * FROM sightings'))}")

    # (f) Someone sitting still holding the phone: in between, no camera movement.
    for _ in range(5):
        sight("phone", "couch", "sofa", 0.5)
    show("(f) phone held while sitting still -> NOT placed")


if __name__ == "__main__":
    main()

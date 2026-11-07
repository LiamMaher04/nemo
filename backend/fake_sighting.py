"""Test the memory without a camera. Run from repo root.

  python -m backend.fake_sighting seed        # add demo items, rooms and anchors
  python -m backend.fake_sighting place remote living_room sofa_arm
  python -m backend.fake_sighting carry remote
  python -m backend.fake_sighting where remote
  python -m backend.fake_sighting reset       # wipe sightings and beliefs (keeps items/rooms)

"place" sends 3 still sightings in a row, which is what the stationary rule needs to call it put down.
Watch item_state change live in the carer app, or with: spacetime sql nemodb-g8356 "SELECT * FROM item_state"
"""
from __future__ import annotations

import json
import sys
import time

from backend.app import spacetime

ITEMS = [
    ("remote", "TV remote", ["clicker", "the remote", "tv remote"], "tv remote control", 0),
    ("keys", "keys", ["house keys", "my keys"], "house keys on keyring", 0),
    ("glasses", "glasses", ["specs", "readers", "reading glasses"], "eyeglasses", 0),
    ("pill_box", "pill box", ["pills", "tablets", "pill organiser"], "pill organizer box", 1),
]
ROOMS = [("living_room", "living room", ["sitting room", "lounge"]), ("kitchen", "kitchen", [])]
ANCHORS = [("sofa_arm", "living_room", "arm of the sofa"), ("coffee_table", "living_room", "coffee table"),
           ("kitchen_counter", "kitchen", "kitchen counter"), ("hall_table", "kitchen", "hall table")]


def seed() -> None:
    for item_id, name, aliases, prompt, imp in ITEMS:
        spacetime.call("upsert_item", item_id, name, json.dumps(aliases), prompt, imp, False)
    for room_id, name, aliases in ROOMS:
        spacetime.call("upsert_room", room_id, name, json.dumps(aliases))
    for anchor_id, room_id, name in ANCHORS:
        spacetime.call("upsert_anchor", anchor_id, room_id, name)
    print("seeded", len(ITEMS), "items,", len(ROOMS), "rooms,", len(ANCHORS), "anchors")


def sighting(item: str, room: str, anchor: str, in_hand: bool, i: int) -> dict:
    return dict(ts_ms=time.time() * 1000, frame_id=i, track_id=1, label=item, det_conf=0.8,
                item_id=item, candidates=[[item, 0.9]], match_margin=0.3, room_id=room,
                room_conf=0.9, anchor_id=anchor, relation="on", bbox=[400, 300, 120, 60],
                in_hand=in_hand, thumb_b64="")


def main(argv: list[str]) -> None:
    cmd = argv[0] if argv else "help"
    if cmd == "seed":
        seed()
    elif cmd == "place":
        item, room, anchor = argv[1], argv[2], argv[3] if len(argv) > 3 else ""
        for i in range(3):
            spacetime.add_sighting(sighting(item, room, anchor, False, i))
            time.sleep(0.3)
        print("placed", item, "in", room, anchor)
    elif cmd == "carry":
        spacetime.add_sighting(sighting(argv[1], "living_room", "", True, 0))
        print("carrying", argv[1])
    elif cmd == "where":
        print(json.dumps({k: v for k, v in (spacetime.where_is(argv[1]) or {}).items()
                          if "thumb" not in k}, indent=2))
    elif cmd == "reset":
        spacetime.call("reset_memory")
        print("memory reset")
    else:
        print(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])

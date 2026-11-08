"""Seed the demo items and areas into Spacetime.

Run from the repo root:  backend\\.venv\\Scripts\\python.exe -m backend.seed_spacetime
Safe to run again: upsert_item and upsert_area replace rows with the same id.
"""

import json
import logging

from backend import spacetime_client

# importance: 1 = everyday, 2 = often looked for, 3 = important (reminders and alerts can use it)
ITEMS = [
    {
        "item_id": "keys",
        "name": "keys",
        "category": "keys",
        "importance": 3,
        "aliases": ["house keys", "car keys", "keyring", "key"],
        "attributes": {"detector_prompt": "house keys on keyring", "size": "small"},
    },
    {
        "item_id": "reading_glasses",
        "name": "reading glasses",
        "category": "glasses",
        "importance": 2,
        "aliases": ["glasses", "specs", "spectacles", "readers"],
        "attributes": {"detector_prompt": "eyeglasses", "size": "small"},
    },
    {
        "item_id": "phone",
        "name": "phone",
        "category": "phone",
        "importance": 3,
        "aliases": ["mobile", "cell phone", "cellphone", "iphone"],
        "attributes": {"detector_prompt": "cell phone", "size": "small"},
    },
    {
        "item_id": "tv_remote",
        "name": "TV remote",
        "category": "remote",
        "importance": 1,
        "aliases": ["remote", "remote control", "clicker", "controller"],
        "attributes": {"detector_prompt": "tv remote control", "size": "small"},
    },
    {
        "item_id": "wallet",
        "name": "wallet",
        "category": "wallet",
        "importance": 3,
        "aliases": ["purse", "billfold", "cards"],
        "attributes": {"detector_prompt": "wallet", "size": "small"},
    },
    {
        "item_id": "pill_box",
        "name": "pill box",
        "category": "medication",
        "importance": 3,
        "aliases": ["pills", "pill organiser", "pill organizer", "medicine", "tablets"],
        "attributes": {"detector_prompt": "pill organizer box", "size": "small", "reminders": True},
    },
]

# Rooms are a first guess for the hotel and demo room; change them here and re-run.
AREAS = [
    ("couch", "couch", "living room"),
    ("desk", "desk", "living room"),
    ("bed_1", "bed 1", "bedroom"),
    ("bed_2", "bed 2", "bedroom"),
    ("tv_area", "TV area", "living room"),
    ("cupboard_corner", "cupboard corner", "living room"),
    ("closet", "closet", "bedroom"),
    ("bathroom", "bathroom", "bathroom"),
    ("demo_table", "demo table", "demo room"),
]


def main() -> None:
    for item in ITEMS:
        spacetime_client.call(
            "upsert_item",
            item["item_id"],
            item["name"],
            item["category"],
            item["importance"],
            item["aliases"],
            json.dumps(item["attributes"]),
        )
    for area_id, name, room in AREAS:
        spacetime_client.call("upsert_area", area_id, name, room)
    print(f"Seeded {len(ITEMS)} items and {len(AREAS)} areas.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    main()

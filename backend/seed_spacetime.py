"""Seed the demo items and areas into Spacetime.

Run from the repo root:  backend\\.venv\\Scripts\\python.exe -m backend.seed_spacetime
Safe to run again: upsert_item and upsert_area replace rows with the same id.
"""

import json
import logging

from backend import spacetime_client

# importance: 1 = everyday, 2 = often looked for, 3 = important (counts as "used", reminders)
ITEMS = [
    {
        "item_id": "keys",
        "name": "keys",
        "category": "keys",
        "importance": 2,
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
        "importance": 2,
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
        "importance": 2,
        "aliases": ["purse", "billfold", "cards"],
        "attributes": {"detector_prompt": "wallet", "size": "small"},
    },
    {
        # item_id stays "pill_box" (Spacetime's PILL_ITEM_ID and the alerts use it). It's a pill bottle.
        "item_id": "pill_box",
        "name": "pills",
        "category": "medication",
        "importance": 3,
        "aliases": ["pill bottle", "medicine", "meds", "tablets", "pills", "pill box",
                    "pill organiser", "pill organizer"],
        "attributes": {"detector_prompt": "clear plastic pill bottle", "size": "small", "reminders": True},
    },
    {
        "item_id": "toothbrush",
        "name": "toothbrush",
        "category": "toothbrush",
        "importance": 1,
        "aliases": ["tooth brush", "electric toothbrush"],
        "attributes": {"detector_prompt": "toothbrush", "size": "small"},
    },
]

# Hotel set (room "hotel room"): the hotel room, for filming the demo video.
# Venue set (room "venue"): the judging table at HackUTD; demo_table is a placeholder, more to come.
AREAS = [
    ("sofa", "sofa", "hotel room"),
    ("desk", "desk", "hotel room"),
    ("fridge", "fridge", "hotel room"),
    ("tv_unit", "TV", "hotel room"),
    ("bedside_table", "bedside table", "hotel room"),
    ("bathroom", "bathroom", "hotel room"),
    ("demo_table", "demo table", "venue"),
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

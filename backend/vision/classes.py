"""What YOLOE looks for. Edit the wordings here.

Each wording describes how the thing LOOKS, not what people call it. Spoken names ("specs",
"clicker") are aliases for the agent, not for vision. Wording matters a lot to YOLOE, so try
several and keep the ones that score well. The camera has no IR-cut filter and colours wash
out, so lean on shape and material rather than colour.

Every wording must be unique across items and furniture.
"""

# item_id (exactly as in backend/seed_spacetime.py) -> wordings.
# The first wording is the item's attributes.detector_prompt from the seed.
ITEMS: dict[str, list[str]] = {
    "keys": [
        "house keys on keyring",
        "bunch of metal keys",
        "metal keys on a ring",
        "single metal door key",
    ],
    "reading_glasses": [
        "eyeglasses",
        "folded eyeglasses",
        "glasses with thin metal frames",
        "glasses with plastic frames",
    ],
    "phone": [
        "cell phone",
        "smartphone",
        "smartphone lying face down",
        "flat rectangular smartphone",
    ],
    "tv_remote": [
        "tv remote control",
        "black tv remote control",
        "long thin remote control with buttons",
        "remote control with rubber buttons",
    ],
    "wallet": [
        "wallet",
        "folded leather wallet",
        "small leather card wallet",
        "bifold wallet",
    ],
    "pill_box": [  # a pill bottle; the item_id stays pill_box
        "clear plastic pill bottle",
        "pill bottle with white cap",
        "small medicine bottle with pills inside",
        "prescription pill bottle",
    ],
    "toothbrush": [
        "toothbrush",
        "electric toothbrush",
        "electric toothbrush standing upright",
        "toothbrush lying on a counter",
    ],
}

# area_ids exactly as in backend/seed_spacetime.py. Reference folders with other names still
# work (for testing) but get a warning, because Spacetime only knows these.
AREA_IDS: list[str] = [
    "couch", "desk", "bed_1", "bed_2", "tv_area", "cupboard_corner", "closet", "bathroom", "demo_table",
]

# Fixed furniture name -> wordings. Spacetime compares furniture names across frames, so
# whichever wording fires, the furniture is always reported under its fixed name.
FURNITURE: dict[str, list[str]] = {
    "table": ["table", "dining table", "coffee table", "wooden table top"],
    "desk": ["desk", "office desk", "writing desk"],
    "sofa": ["sofa", "couch", "arm of a sofa", "sofa cushions"],
    "bed": ["bed", "bed with duvet", "mattress"],
    "bedside table": ["bedside table", "nightstand", "small cabinet beside a bed"],
    "chair": ["chair", "armchair", "office chair"],
    "shelf": ["shelf", "bookshelf", "wall shelf"],
    "counter": ["counter", "kitchen counter", "countertop", "bathroom counter"],
    # Wordings describe the cabinet, not the screen, so the television itself doesn't fire.
    "tv stand": ["tv stand", "media console", "low cabinet under a television", "low wooden media cabinet"],
    # Wordings say "doors" so they lean to closed cupboards, not open shelves.
    "cupboard": ["cupboard", "wardrobe", "cabinet with doors", "closet doors"],
}

# An item whose centre is outside every furniture box is matched to the nearest furniture
# box edge within this fraction of the frame width. Further away: furniture is "".
NEAR_FURNITURE_FRAC = 0.15

# Boxes of the SAME item (or the same furniture) from different wordings overlapping more
# than this are one thing: keep the best.
SAME_THING_IOU = 0.5

# Boxes of DIFFERENT items overlapping more than this are ambiguous: one sighting with
# item_id "" and both as candidates.
AMBIGUOUS_IOU = 0.6

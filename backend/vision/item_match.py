"""Which item is it? Compare an item crop with each item's reference crops."""

import numpy as np

from backend.vision import classes, dino, settings

# item_id -> reference fingerprints (n, 384)
_refs: dict[str, np.ndarray] = {}


def has_refs(item_id: str | None = None) -> bool:
    """Any item references at all, or references for this item."""
    return bool(_refs) if item_id is None else item_id in _refs


def load_refs() -> None:
    """Fingerprint every item's reference crops once."""
    _refs.clear()
    folder = settings.REFS_DIR / "items"
    if not folder.is_dir():
        print(f"items: no reference folder at {folder}; the YOLOE wording decides the item")
        return
    for item_dir in sorted(p for p in folder.iterdir() if p.is_dir()):
        files = dino.image_files(item_dir)
        if not files:
            continue
        _refs[item_dir.name] = dino.embed_files(files, as_crop=True)
        note = "" if item_dir.name in classes.ITEMS else "  (not a seed item_id: a look-alike; if it wins, item_id is \"\")"
        print(f"items: {item_dir.name}: {len(_refs[item_dir.name])} reference crops{note}")


def rank(crop_fp: np.ndarray) -> list[tuple[str, float]]:
    """Every item with references, best match first: (item_id, best similarity to its references)."""
    scores = [(item_id, float((refs @ crop_fp).max())) for item_id, refs in _refs.items()]
    return sorted(scores, key=lambda s: s[1], reverse=True)


def decide(ranked: list[tuple[str, float]]) -> tuple[str, float]:
    """(item_id, match_margin). item_id is "" if the best match is weak, too close to the next,
    or a look-alike folder that isn't one of our items (e.g. refs/items/sunglasses/)."""
    best_id, best_sim = ranked[0]
    margin = best_sim - (ranked[1][1] if len(ranked) > 1 else 0.0)
    if best_sim < settings.ITEM_SIM_MIN or margin < settings.ITEM_MARGIN_MIN or best_id not in classes.ITEMS:
        return "", margin
    return ranked[0][0], margin

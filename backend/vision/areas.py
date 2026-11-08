"""Where is the wearer? Match each kept frame to the area reference frames, then vote over time."""

from collections import deque
from dataclasses import dataclass

import numpy as np

from backend.vision import classes, dino, settings

# area_id -> reference fingerprints (n, 384)
_refs: dict[str, np.ndarray] = {}
# Recent votes: (ts_ms, area_id or "" for no clear match)
_votes: deque[tuple[float, str]] = deque()


@dataclass
class AreaMatch:
    area_id: str  # "" if no clear match
    area_conf: float  # share of the window's votes for area_id
    vote: str  # what this frame alone voted ("" = no clear match)
    best: str  # this frame's best area and its score, for printing
    best_sim: float
    next_sim: float  # second-best area's score
    window: int  # frames in the voting window


def has_refs() -> bool:
    return bool(_refs)


def load_refs() -> None:
    """Fingerprint every area's reference frames once, and print how alike the areas are."""
    _refs.clear()
    folder = settings.REFS_DIR / "areas"
    if not folder.is_dir():
        print(f"areas: no reference folder at {folder}; area_id stays \"\"")
        return
    for area_dir in sorted(p for p in folder.iterdir() if p.is_dir()):
        files = dino.image_files(area_dir)
        if not files:
            continue
        _refs[area_dir.name] = dino.embed_files(files, as_crop=False)
        note = "" if area_dir.name in classes.AREA_IDS else "  (test only, not a seed area_id)"
        print(f"areas: {area_dir.name}: {len(_refs[area_dir.name])} reference frames{note}")
    if _refs:
        _print_similarity()


def _mean_sim(a: np.ndarray, b: np.ndarray, same: bool) -> float:
    sims = a @ b.T
    if same:  # leave out each frame compared with itself
        n = len(a)
        return float((sims.sum() - np.trace(sims)) / (n * n - n)) if n > 1 else float("nan")
    return float(sims.mean())


def _print_similarity() -> None:
    """Average similarity of each area's references to every other area's, with a warning
    for pairs too close to tell apart."""
    names = list(_refs)
    table = {(a, b): _mean_sim(_refs[a], _refs[b], a == b) for a in names for b in names}
    width = max(len(n) for n in names) + 2
    print("areas: average similarity of references (diagonal = within the area)")
    print(" " * width + "".join(f"{n[:10]:>11}" for n in names))
    for a in names:
        print(f"{a:<{width}}" + "".join(f"{table[(a, b)]:>11.3f}" for b in names))
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            own = min(table[(a, a)], table[(b, b)])
            if np.isnan(own):
                print(f"areas: note: {a} or {b} has only one reference frame, so it can't be checked")
            elif table[(a, b)] >= own - settings.AREA_MARGIN_MIN:
                print(f"areas: WARNING: {a} and {b} look too alike ({table[(a, b)]:.3f} between them, "
                      f"{own:.3f} within). Add references that show what differs, or merge them.")


def match(frame_fp: np.ndarray | None, ts_ms: float) -> AreaMatch:
    """Vote for this frame's area and return the winner over the last AREA_VOTE_S seconds."""
    if not _refs or frame_fp is None:
        return AreaMatch("", 0.0, "", "", 0.0, 0.0, 0)
    scores = sorted(((float((refs @ frame_fp).max()), area) for area, refs in _refs.items()), reverse=True)
    best_sim, best = scores[0]
    next_sim = scores[1][0] if len(scores) > 1 else 0.0
    clear = best_sim >= settings.AREA_SIM_MIN and best_sim - next_sim >= settings.AREA_MARGIN_MIN
    vote = best if clear else ""

    _votes.append((ts_ms, vote))
    while _votes and _votes[0][0] <= ts_ms - settings.AREA_VOTE_S * 1000:
        _votes.popleft()
    counts: dict[str, int] = {}
    latest: dict[str, int] = {}  # position of each area's newest vote, to break ties
    for i, (_, v) in enumerate(_votes):
        if v:
            counts[v] = counts.get(v, 0) + 1
            latest[v] = i
    winner, area_conf = "", 0.0
    if counts:
        top = max(counts, key=lambda a: (counts[a], latest[a]))  # a tie goes to the most recent
        share = counts[top] / len(_votes)
        if share >= settings.AREA_VOTE_MIN:
            winner, area_conf = top, share
    return AreaMatch(winner, round(area_conf, 3), vote, best, best_sim, next_sim, len(_votes))

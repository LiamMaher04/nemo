# Vision

Frame in, sightings out. Sharpness gate, near-duplicate gate, YOLOE with text prompts, then
DINOv2 for the area (where the wearer is) and the item (which of our things it is).
Without reference photos, `area_id` is `""`, `area_conf` is `0.0`, and the YOLOE wording decides
the item with `match_margin` `1.0`.

## process()

```python
from backend.vision import process

result = process(jpeg_bytes, frame_id, ts_ms)   # ts_ms: UTC ms since epoch
```

Returns a `VisionResult`:

| field | meaning |
|---|---|
| `kept` | `False` if the frame was dropped |
| `drop_reason` | `""` if kept, else e.g. `blurry (31.2 < 40)` or `duplicate (diff 1.30 < 2, 0.8s since kept)` |
| `sharpness` | variance of the Laplacian on the full-resolution greyscale frame, filled for every frame |
| `sightings` | one dict per item, keys in `add_sighting` order (14). `[]` if dropped |
| `frame` | one dict, keys in `add_frame` order (7). `None` if dropped |
| `furniture_boxes` | `(name, [x, y, w, h], conf)`, only for drawing |
| `ms` | time spent in `process()` (also `yoloe_ms` and `dino_ms`) |
| `area` | this frame's area vote and scores, for printing |

The dicts keep their key order, so `list(d.values())` is the reducer's argument array.

How the sightings are made:
- Several wordings of the same item (or furniture) on overlapping boxes (IoU over 0.5): the best one is kept.
- Boxes of DIFFERENT items overlapping with IoU over 0.6 are one object.
- `item_id`, `candidates_json`, `match_margin`:
  - If the YOLOE item (all of them, for an overlapping group) has reference crops, DINOv2 compares
    the crop with every item's references. `candidates_json` is the top 3 `[item_id, similarity]`,
    `match_margin` is top 1 minus top 2 similarity. `item_id` is `""` if the best similarity is
    below `ITEM_SIM_MIN`, the margin is below `ITEM_MARGIN_MIN`, or the winner is a look-alike
    folder that isn't one of our items (e.g. `refs/items/sunglasses/`).
  - Otherwise (no references), the YOLOE wording decides, `match_margin` `1.0`. An overlapping
    group of different items is ambiguous: `item_id` `""`, candidates with YOLOE confidences,
    `match_margin` = their confidence gap.
  - Ambiguous items (`item_id` `""`) are left out of `items_seen_json`.
- `area_id`, `area_conf` (same for the frame and all its sightings): each kept frame's
  best area (best similarity to that area's references) gets a vote if it scores at least
  `AREA_SIM_MIN` and beats the next area by `AREA_MARGIN_MIN`; otherwise the frame votes "none".
  Over the kept frames of the last `AREA_VOTE_S` seconds, the area with most votes wins (a tie
  goes to the most recent), and `area_conf` is its share of the votes. Below `AREA_VOTE_MIN` the
  area is `""`.
- `furniture`: the smallest furniture box containing the item's centre, else the nearest box
  within 15% of the frame width, else `""`. Furniture is always reported under its fixed name.
- `rel_pos_json`: `[x, y]` of the item centre in that furniture box, 0 to 1, or `"[]"`.
- `thumb_b64`: JPEG crop of the item with 20% padding, 160 px wide, faces blurred first
  (`pipeline.blur_faces`, Haar cascade for now; it misses turned faces, and YuNet replaces it
  before vision is wired to Spacetime).

## Reference photos (gitignored: photos of our rooms)

```
backend/vision/refs/areas/<area_id>/*.jpg    whole Nemo frames, 10 to 20 per area
backend/vision/refs/items/<item_id>/*.jpg    crops of just the item, 5 to 10 per item
```

Use exact ids from `backend/seed_spacetime.py`. Other folder names still load: an area gets a
"test only" note; an item folder is a look-alike (if it wins, `item_id` is `""`). Take the photos
with Nemo itself (`--save`), since the fisheye must match. Areas: where the wearer actually
stands or sits, turning slowly, sitting and standing, lamp on and off. Items: different sides,
furniture, distances, some in a hand.

Fingerprints are worked out once at startup. The runner then prints each area's average
similarity to every other area and warns if two are too close to tell apart (e.g. two identical
beds). `REFS_DIR` points somewhere else for testing, e.g. `backend/vision/test_refs`.

Wordings, furniture names and the overlap and distance thresholds are in `classes.py`.

## Run it

From the repo root, with the backend venv:

```
pip install -r backend/vision/requirements.txt
python -m backend.vision.run                   # webcam 0
python -m backend.vision.run --camera 1        # another camera
python -m backend.vision.run --folder path/    # every .jpg / .jpeg in a folder, in name order
python -m backend.vision.run --folder path/ --show   # boxes drawn; any key = next image, q = quit
python -m backend.vision.run --url http://<device-ip>/jpg   # poll a JPEG URL (e.g. Nemo) as fast as it answers
python -m backend.vision.run --url http://<device-ip>/jpg --save backend/vision/captures/
```

`--save DIR` works with any source. Every KEPT frame is saved as `DIR/<run start>_<frame_id>.jpg`
(e.g. `20261108-013502_000042.jpg`), faces blurred first. A DIR inside the repo must be
gitignored or the runner refuses to start; `backend/vision/captures/` and `test_images/` already are.

It prints the sharpness of every frame, why dropped frames were dropped, each sighting and frame
report on one line (`thumb_b64` as its length), and the time per frame. The first kept frame is
slow (the GPU warms up).

On macOS the terminal needs camera permission (System Settings > Privacy & Security > Camera).

## Settings (repo-root `.env`)

| name | default | meaning |
|---|---|---|
| `DETECTOR_WEIGHTS` | `yoloe-26s-seg.pt` | a bare name is looked for in `backend/`, then the repo root, else downloaded into `backend/` |
| `DETECT_CONF` | `0.25` | YOLOE confidence threshold |
| `DETECT_IMGSZ` | `960` | YOLOE inference size (try 1280 for keys) |
| `SHARPNESS_GATE` | `40` | drop frames below this sharpness. Spacetime's `FRAME_SHARP_MIN` (100) is a separate bar for "clearly in view" |
| `DUPLICATE_DIFF_MAX` | `2.0` | drop frames whose 64x48 greyscale thumbnail differs from the last kept one by less than this (mean absolute difference, 0 to 255) |
| `KEEPALIVE_S` | `3` | if nothing has been kept for this long, keep the next sharp duplicate anyway |
| `DINO_MODEL` | `facebook/dinov2-small` | DINOv2 model (Hugging Face, downloaded once to `~/.cache/huggingface`) |
| `DINO_REVISION` | `ed25f3a...` | pinned model revision |
| `REFS_DIR` | `backend/vision/refs` | reference photos, relative to the repo root |
| `AREA_VOTE_S` | `3` | area voting window in seconds (about 3 kept frames from Nemo) |
| `AREA_SIM_MIN` | `0.55` | a frame's best area must score at least this to vote |
| `AREA_MARGIN_MIN` | `0.03` | ... and beat the next area by this |
| `AREA_VOTE_MIN` | `0.5` | the winning area's share of the votes, else `area_id` is `""` |
| `ITEM_SIM_MIN` | `0.40` | below this best similarity the item is ambiguous |
| `ITEM_MARGIN_MIN` | `0.05` | below this margin the item is ambiguous |

The device is picked automatically: mps, then cuda, then cpu. The YOLOE text encoder
(`mobileclip2_b.ts`) is downloaded next to the weights on first use.

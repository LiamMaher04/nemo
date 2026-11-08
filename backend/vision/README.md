# Vision v1

Frame in, sightings out. Sharpness gate, near-duplicate gate, then YOLOE with text prompts.
Areas (DINOv2) are placeholders for now: `area_id` is `""`, `area_conf` is `0.0`, and
`match_margin` is `1.0` for identified items.

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
| `ms` | time spent in `process()` |

The dicts keep their key order, so `list(d.values())` is the reducer's argument array.

How the sightings are made:
- Several wordings of the same item (or furniture) on overlapping boxes (IoU over 0.5): the best one is kept.
- Boxes of DIFFERENT items overlapping with IoU over 0.6: one sighting with `item_id` `""`,
  `candidates_json` listing all of them with their confidences (best first), `match_margin` = the
  confidence gap between the top two. Ambiguous items are left out of `items_seen_json`.
- `furniture`: the smallest furniture box containing the item's centre, else the nearest box
  within 15% of the frame width, else `""`. Furniture is always reported under its fixed name.
- `rel_pos_json`: `[x, y]` of the item centre in that furniture box, 0 to 1, or `"[]"`.
- `thumb_b64`: JPEG crop of the item with 20% padding, 160 px wide, faces blurred first (Haar cascade).

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

The device is picked automatically: mps, then cuda, then cpu. The YOLOE text encoder
(`mobileclip2_b.ts`) is downloaded next to the weights on first use.

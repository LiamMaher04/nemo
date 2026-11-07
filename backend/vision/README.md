# Vision: detection and teaching Nemo with our own photos

`teach.py` makes detection better in minutes, with no GPU and no training run. You label frames from
the real camera, and each saved frame is learned in about 0.3 s. The live view improves straight away.

## How it works (one paragraph)

YOLOE decides what a box is by comparing the box's "fingerprint" (an embedding) with fingerprints
of what we're looking for. Normally those come only from words in `objects.yaml`. Teaching adds
fingerprints made from our own labelled boxes: what *our* keys look like, through *our* camera.
Both sit side by side and the best match wins. Labelled look-alikes ("airpods case") get
fingerprints too, so they win their own boxes instead of being called "mug". The model's weights
never change, which is why it's instant. (Fine-tuning, which does change the weights, comes later
and can reuse the same labelled photos.)

## Using it

Run from the `backend/` folder (setup in `backend/README.md`):

```bash
python live.py                    # just watch what it detects (webcam)
python teach.py                   # label frames so it learns (webcam)
python teach.py --source push     # frames from the Nemo device (docs/interfaces.md, POST /frame)
python check.py                   # did teaching help? scores the test photos
```

What to look for is in `vision/objects.yaml` (with the `item_id`s Spacetime uses).
`--source push` listens on `BACKEND_PORT` from `.env`. If the FastAPI backend is already running on
that port, use `--source push:8001` and point the device (or `tools/fake_board.py --url`) there.

1. **Space** freezes the frame. Boxes the detector suggests are already drawn.
2. Fix them: **drag** to draw a missing box, **click** a box then press **1-9** to relabel it, **D** to delete a wrong one. **N** adds a look-alike label (type its name in the Terminal).
3. **Enter** saves and learns. **Esc** throws the frame away.
4. **L** in the live view turns learning on and off, to see the difference. Boxes found by learning have a `*`.
5. `python check.py` scores "words only" against "words + learning" on the test photos.

Tips that matter most:

- **Box every tracked item and every look-alike in the frame.** An unboxed item teaches nothing; a boxed look-alike is exactly what stops mix-ups.
- **Use the camera you'll demo with**, at the height and angle you'll demo with. The device's 160 degree lens makes things look different from a webcam.
- Move things around between frames: different spots, distances, lighting, partly hidden. 10 to 20 photos per item is a good start.
- Empty or "nothing tracked here" frames are worth saving too.
- Every 5th photo is a **test photo**: saved but never learned from, so `check.py` is honest. That's normal.

## What gets saved (backend/data/teach/)

| File | What it is |
|---|---|
| `images/00001.jpg` | the photos |
| `labels/00001.txt` | boxes in standard YOLO format, reusable for fine-tuning later |
| `classes.txt` | label names; line number = class number in the label files |
| `learned.npz` | what was learned: a few KB. **This is the file to share.** |

`backend/data/` isn't committed to git (photos can be large and personal). To share what you learned, send
`backend/data/teach/learned.npz`, or the whole `backend/data/teach/` folder if they also want the photos.
`python teach.py --relearn` rebuilds `learned.npz` from the photos.

## Using it in the backend pipeline (POST /frame)

```python
from vision.detector import Detector, load_objects
from vision.learning import Learned, TeachStore

detector = Detector()                                    # DETECTOR_WEIGHTS from .env, else yoloe-26s-seg.pt
learned = Learned.load(TeachStore().learned_path, detector.model_name)
detector.set_objects(load_objects(), learned.for_detector())

for d in detector.detect(frame):                         # frame: BGR numpy image; conf = DETECT_CONF
    if d["kind"] == "item":                              # skip "lookalike" boxes
        print(d["item_id"], d["conf"], d["box"], "learned" if d["learned"] else "words")
```

`d["item_id"]`, `d["prompt"]` (the label YOLOE used) and `d["conf"]` map onto `add_sighting`'s
`item_id`, `label` and `det_conf`. `d["box"]` is `[x1, y1, x2, y2]`; `bbox_json` wants `[x, y, w, h]`.

`learned.npz` only works with the model it was learned with (`yoloe-26s-seg.pt`). If you switch
models, run `python teach.py --relearn` with the new one.

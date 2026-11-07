"""Teach Nemo with your own camera: freeze a frame, fix the boxes, save. It learns in about a second.

    python teach.py                    # laptop webcam
    python teach.py --source push      # photos from the clip (see docs/board-protocol.md)
    python teach.py --relearn          # rebuild what was learned from all saved photos, then start

LIVE VIEW
    Space    freeze this frame to label it
    L        learning on/off (compare before and after)
    Q        quit

LABELLING A FROZEN FRAME (boxes the detector suggests are already drawn)
    drag            draw a new box (gets the current label)
    click a box     select it
    1-9             pick a label; if a box is selected, relabel it
    N               new look-alike label, typed in the Terminal (e.g. "airpods case")
    D / Backspace   delete the selected box
    Enter           save and learn
    Esc             throw this frame away

Box EVERY tracked item in the frame, and every look-alike (things that get mistaken for an item).
Labelling look-alikes is what stops "airpods case = mug". A frame with nothing in it is still useful:
just press Enter.
"""
import argparse
import logging
import time

import cv2
import numpy as np

from nemo.camera import open_source
from nemo.detector import Detector, load_objects
from nemo.learning import Learned, TeachStore, is_test_photo, relearn

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("nemo")

WINDOW = "Nemo: teach"
MAX_WIDTH = 1280
ITEM = (90, 220, 120)
LOOKALIKE = (60, 160, 255)
SELECTED = (255, 255, 0)


def with_panel(img, lines):
    """Add a dark strip under the photo with help text, wrapped to fit. lines: [(text, colour)].

    The strip is below the photo so it never covers it, and mouse positions on the photo don't move.
    """
    w = img.shape[1]
    wrapped = []
    for text, color in lines:
        words, line = text.split(" "), ""
        for word in words:
            trial = (line + " " + word).strip()
            if cv2.getTextSize(trial, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)[0][0] > w - 16 and line:
                wrapped.append((line, color))
                line = word
            else:
                line = trial
        wrapped.append((line, color))
    panel = np.full((10 + 22 * len(wrapped), w, 3), 30, np.uint8)
    for i, (text, color) in enumerate(wrapped):
        cv2.putText(panel, text, (8, 24 + 22 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)
    return np.vstack([img, panel])


def box_label(img, text, x1, y1, color):
    (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
    ty = max(th + 8, y1)
    cv2.rectangle(img, (x1, ty - th - 8), (x1 + tw + 8, ty), color, -1)
    cv2.putText(img, text, (x1 + 4, ty - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (20, 20, 20), 2, cv2.LINE_AA)


class Labeller:
    """The labelling state for one frozen frame. Pure logic, so it can be tested without a screen."""

    def __init__(self, frame, suggestions, labels, current=0):
        self.frame = frame
        self.labels = labels                  # what the number keys choose from
        self.current = min(current, len(labels) - 1)
        self.boxes = [{"label": s["label"], "box": list(s["box"])} for s in suggestions]
        self.selected = None
        self._drag = None

    def _hit(self, x, y):
        hits = [i for i, b in enumerate(self.boxes)
                if b["box"][0] <= x <= b["box"][2] and b["box"][1] <= y <= b["box"][3]]
        area = lambda i: (self.boxes[i]["box"][2] - self.boxes[i]["box"][0]) * (self.boxes[i]["box"][3] - self.boxes[i]["box"][1])
        return min(hits, key=area) if hits else None

    def mouse(self, event, x, y):
        if event in (cv2.EVENT_LBUTTONDOWN, cv2.EVENT_RBUTTONDOWN) and y >= self.frame.shape[0]:
            return   # click on the help strip, not the photo
        if event == cv2.EVENT_LBUTTONDOWN:
            self._drag = (x, y, x, y)
        elif event == cv2.EVENT_MOUSEMOVE and self._drag:
            self._drag = (*self._drag[:2], x, y)
        elif event == cv2.EVENT_LBUTTONUP and self._drag:
            x0, y0 = self._drag[:2]
            self._drag = None
            if abs(x - x0) < 6 and abs(y - y0) < 6:      # a click, not a drag
                self.selected = self._hit(x, y)
            else:
                h, w = self.frame.shape[:2]
                box = [max(0, min(x0, x)), max(0, min(y0, y)), min(w - 1, max(x0, x)), min(h - 1, max(y0, y))]
                self.boxes.append({"label": self.labels[self.current], "box": box})
                self.selected = len(self.boxes) - 1
        elif event == cv2.EVENT_RBUTTONDOWN:
            i = self._hit(x, y)
            if i is not None:
                self.delete(i)

    def choose(self, index):
        if 0 <= index < len(self.labels):
            self.current = index
            if self.selected is not None:
                self.boxes[self.selected]["label"] = self.labels[index]

    def add_label(self, name):
        name = name.strip().lower()
        if name:
            if name not in self.labels:
                self.labels.append(name)
            self.choose(self.labels.index(name))

    def delete(self, i=None):
        i = self.selected if i is None else i
        if i is not None and 0 <= i < len(self.boxes):
            self.boxes.pop(i)
        self.selected = None

    def render(self, item_names, scale):
        img = cv2.resize(self.frame, None, fx=scale, fy=scale) if scale != 1 else self.frame.copy()
        for i, b in enumerate(self.boxes):
            x1, y1, x2, y2 = (int(v * scale) for v in b["box"])
            color = SELECTED if i == self.selected else ITEM if b["label"] in item_names else LOOKALIKE
            cv2.rectangle(img, (x1, y1), (x2, y2), color, 3 if i == self.selected else 2)
            box_label(img, b["label"], x1, y1, color)
        if self._drag:
            x0, y0, x, y = (int(v * scale) for v in self._drag)
            cv2.rectangle(img, (x0, y0), (x, y), SELECTED, 1)
        keys = "   ".join(f"[{i + 1} {lab}]" if i == self.current else f"{i + 1} {lab}"
                           for i, lab in enumerate(self.labels[:9]))
        return with_panel(img, [
            ("LABELLING: drag = new box, click = select, 1-9 = label, N = new look-alike, D = delete", (255, 255, 255)),
            ("Labels: " + keys, (180, 255, 180)),
            ("Enter = save + learn    Esc = discard", (255, 255, 255)),
        ])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", default="webcam", help="webcam, webcam:N, push or push:PORT")
    ap.add_argument("--objects", default="objects.yaml")
    ap.add_argument("--data", default="data/teach", help="where labelled photos and learning are saved")
    ap.add_argument("--conf", type=float, default=0.2)
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--device", default=None)
    ap.add_argument("--relearn", action="store_true", help="rebuild learning from all saved photos first")
    args = ap.parse_args()

    objects = load_objects(args.objects)
    names = [o["name"] for o in objects]
    try:
        source = open_source(args.source)
    except (RuntimeError, ValueError) as e:
        raise SystemExit(f"\n{e}")
    detector = Detector(device=args.device)
    store = TeachStore(args.data)
    if args.relearn:
        log.info("Relearning from %d saved photos...", len(store.numbers()))
        learned = relearn(detector, store, names)
    else:
        learned = Learned.load(store.learned_path, detector.model_name)
    use_learned = True

    def apply():
        detector.set_objects(objects, learned.for_detector() if use_learned else None)
    apply()
    log.info("Learned so far: %s", learned.summary())

    labels = names + [c for c in store.classes if c not in names]
    current = 0
    labeller, frame, dets, ms = None, None, [], 0.0
    state = {"labeller": None, "scale": 1.0}

    def on_mouse(event, x, y, flags, param):
        if state["labeller"] is not None:
            s = state["scale"]
            state["labeller"].mouse(event, int(x / s), int(y / s))

    cv2.namedWindow(WINDOW)
    cv2.setMouseCallback(WINDOW, on_mouse)
    try:
        while True:
            if labeller is None:
                new = source.read()
                if new is not None:
                    frame = new
                    t0 = time.time()
                    dets = detector.detect(frame, args.conf, args.imgsz)
                    ms = (time.time() - t0) * 1000
                if frame is None:
                    cv2.waitKey(100)
                    continue
                scale = min(1.0, MAX_WIDTH / frame.shape[1])
                img = cv2.resize(frame, None, fx=scale, fy=scale) if scale != 1 else frame.copy()
                for d in dets:
                    x1, y1, x2, y2 = (int(v * scale) for v in d["box"])
                    color = ITEM if d["kind"] == "item" else LOOKALIKE
                    cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
                    box_label(img, f"{d['name']}{'*' if d['learned'] else ''} {d['conf']:.2f}", x1, y1, color)
                img = with_panel(img, [
                    (f"LIVE: {source.status()} | {ms:.0f} ms", (255, 255, 255)),
                    (f"Learning {'ON' if use_learned else 'OFF'}: {learned.summary()}",
                     (180, 255, 180) if use_learned else (200, 200, 200)),
                    ("Space = freeze and label    L = learning on/off    Q = quit    (* = found by learning)",
                     (255, 255, 255)),
                ])
                cv2.imshow(WINDOW, img)
                key = cv2.waitKey(1 if new is not None else 30) & 0xFF
                if key in (ord("q"), 27):
                    break
                if key == ord(" "):
                    sugg = [{"label": d["name"], "box": d["box"]} for d in dets]
                    labeller = Labeller(frame.copy(), sugg, labels, current)
                    state.update(labeller=labeller, scale=scale)
                if key == ord("l"):
                    use_learned = not use_learned
                    apply()
                continue

            # ----- labelling a frozen frame -----
            cv2.imshow(WINDOW, labeller.render(names, state["scale"]))
            key = cv2.waitKey(30) & 0xFF
            if ord("1") <= key <= ord("9"):
                labeller.choose(key - ord("1"))
            elif key == ord("n"):
                labeller.add_label(input("Name of the look-alike (e.g. airpods case), then Enter: "))
            elif key in (ord("d"), 8, 127):
                labeller.delete()
            elif key == 27:
                labeller = None
            elif key in (13, 10):
                n = store.save(labeller.frame, labeller.boxes)
                current = labeller.current
                if is_test_photo(n):
                    log.info("Saved photo %d as a TEST photo (kept aside to measure accuracy, not learned from)", n)
                else:
                    t0 = time.time()
                    got = learned.add_photo(detector, labeller.frame, labeller.boxes, names)
                    learned.save(store.learned_path)
                    log.info("Saved photo %d, learned %s in %.1f s", n, ", ".join(got) or "nothing (no boxes)",
                             time.time() - t0)
                    apply()
                labels = labeller.labels
                labeller = None
            state["labeller"] = labeller
    except KeyboardInterrupt:
        pass
    finally:
        source.close()
        cv2.destroyAllWindows()
        log.info("Saved in %s. Learned: %s", args.data, learned.summary())


if __name__ == "__main__":
    main()

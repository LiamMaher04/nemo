"""Instant learning from our own labelled photos. No GPU, no training run, seconds per photo.

Each labelled box is run through YOLOE once to get its fingerprint (embedding). Fingerprints are
averaged per label and handed to the detector next to the typed wordings (see nemo/detector.py).
The model's weights never change, which is why this is instant.

On disk (backend/data/teach/ by default), in standard YOLO format so it can also be used to fine-tune later:
    images/00001.jpg   the saved photos
    labels/00001.txt   one line per box: class x_centre y_centre width height (fractions of the photo)
    classes.txt        one label per line; line number = class number
    learned.npz        what was learned, for the detector (and for your teammate's code)

Every 5th photo (00005, 00010, ...) is kept aside as a test photo and never learned from, so we
can measure honestly whether learning helped.
"""
import logging
import os

import cv2
import numpy as np

log = logging.getLogger("nemo")


def is_test_photo(number):
    return number % 5 == 0


class TeachStore:
    def __init__(self, root=None):
        from vision import TEACH_DIR
        self.root = str(root or TEACH_DIR)
        self.images = os.path.join(root, "images")
        self.labels = os.path.join(root, "labels")
        os.makedirs(self.images, exist_ok=True)
        os.makedirs(self.labels, exist_ok=True)
        self.classes_path = os.path.join(root, "classes.txt")
        self.classes = []
        if os.path.exists(self.classes_path):
            with open(self.classes_path) as f:
                self.classes = [line.strip() for line in f if line.strip()]

    @property
    def learned_path(self):
        return os.path.join(self.root, "learned.npz")

    def numbers(self):
        return sorted(int(f[:-4]) for f in os.listdir(self.images) if f.endswith(".jpg") and f[:-4].isdigit())

    def _class_id(self, label):
        if label not in self.classes:
            self.classes.append(label)
            with open(self.classes_path, "w") as f:
                f.write("\n".join(self.classes) + "\n")
        return self.classes.index(label)

    def save(self, image, boxes):
        """boxes: [{'label': 'keys', 'box': [x1, y1, x2, y2] in pixels}]. Returns the photo number."""
        n = (self.numbers() or [0])[-1] + 1
        h, w = image.shape[:2]
        cv2.imwrite(os.path.join(self.images, f"{n:05d}.jpg"), image, [cv2.IMWRITE_JPEG_QUALITY, 95])
        lines = []
        for b in boxes:
            x1, y1, x2, y2 = b["box"]
            c = self._class_id(b["label"])
            lines.append(f"{c} {(x1 + x2) / 2 / w:.6f} {(y1 + y2) / 2 / h:.6f} {(x2 - x1) / w:.6f} {(y2 - y1) / h:.6f}")
        with open(os.path.join(self.labels, f"{n:05d}.txt"), "w") as f:
            f.write("\n".join(lines) + ("\n" if lines else ""))
        return n

    def load(self, n):
        """(image, [{'label', 'box' in pixels}]) for a saved photo."""
        image = cv2.imread(os.path.join(self.images, f"{n:05d}.jpg"))
        h, w = image.shape[:2]
        boxes = []
        path = os.path.join(self.labels, f"{n:05d}.txt")
        if os.path.exists(path):
            for line in open(path).read().split("\n"):
                parts = line.split()
                if len(parts) != 5:
                    continue
                c, cx, cy, bw, bh = int(parts[0]), *map(float, parts[1:])
                boxes.append({"label": self.classes[c],
                              "box": [(cx - bw / 2) * w, (cy - bh / 2) * h, (cx + bw / 2) * w, (cy + bh / 2) * h]})
        return image, boxes


class Learned:
    """Running per-label fingerprints: the sum of every labelled example, so adding one is instant."""

    def __init__(self, model_name):
        self.model_name = model_name
        self.data = {}   # label -> {"sum": vector, "images": int, "boxes": int, "object": name or None}

    def add_photo(self, detector, image, boxes, object_names):
        """Learn from one labelled photo. object_names: the items in objects.yaml (others are look-alikes)."""
        by_lower = {o.lower(): o for o in object_names}
        usable = [b for b in boxes if b["box"][2] - b["box"][0] >= 4 and b["box"][3] - b["box"][1] >= 4]
        embs = detector.visual_embeddings(image, [b["box"] for b in usable], [b["label"] for b in usable])
        for label, emb in embs.items():
            d = self.data.setdefault(label, {"sum": np.zeros_like(emb), "images": 0, "boxes": 0,
                                             "object": by_lower.get(label.lower())})
            d["sum"] = d["sum"] + emb
            d["images"] += 1
            d["boxes"] += sum(1 for b in usable if b["label"] == label)
        return sorted(embs)

    def for_detector(self):
        """{label: {"emb", "object"}} for Detector.set_objects()."""
        return {lab: {"emb": d["sum"] / max(float(np.linalg.norm(d["sum"])), 1e-6), "object": d["object"]}
                for lab, d in self.data.items() if d["images"]}

    def summary(self):
        return ", ".join(f"{lab} ({d['images']} photos)" for lab, d in sorted(self.data.items())) or "nothing yet"

    def save(self, path):
        labels = sorted(self.data)
        np.savez(path, model=self.model_name, labels=np.array(labels),
                 objects=np.array([self.data[l]["object"] or "" for l in labels]),
                 sums=np.stack([self.data[l]["sum"] for l in labels]) if labels else np.zeros((0, 1)),
                 images=np.array([self.data[l]["images"] for l in labels]),
                 boxes=np.array([self.data[l]["boxes"] for l in labels]))

    @classmethod
    def load(cls, path, model_name):
        learned = cls(model_name)
        if not os.path.exists(path):
            return learned
        z = np.load(path, allow_pickle=False)
        if str(z["model"]) != model_name:
            log.warning("%s was learned with %s, not %s; ignoring it. Run teach.py --relearn.",
                        path, z["model"], model_name)
            return learned
        for i, lab in enumerate(z["labels"]):
            learned.data[str(lab)] = {"sum": z["sums"][i].astype(np.float32), "images": int(z["images"][i]),
                                      "boxes": int(z["boxes"][i]), "object": str(z["objects"][i]) or None}
        return learned


def relearn(detector, store, object_names):
    """Rebuild learned.npz from every saved photo (except test photos). About 0.3 s per photo."""
    learned = Learned(detector.model_name)
    for n in store.numbers():
        if is_test_photo(n):
            continue
        image, boxes = store.load(n)
        if image is not None and boxes:
            learned.add_photo(detector, image, boxes, object_names)
    learned.save(store.learned_path)
    return learned

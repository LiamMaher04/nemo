"""Object detection with YOLOE: you give it plain-English prompts, it finds them in a photo.

YOLOE is "open-vocabulary": it isn't limited to a fixed list of classes. It compares each box it
finds against "fingerprints" (embeddings) of what we're looking for. Those fingerprints come from:

  - words in objects.yaml ("cup", "keys"), turned into fingerprints by a small text model;
  - learned examples: boxes we labelled on our own camera's photos (see teach.py and
    nemo/learning.py), turned into fingerprints of what *our* keys actually look like.

Both kinds sit side by side. YOLOE-26 gives each box exactly one label, so whichever fingerprint
fits best wins. Look-alikes we labelled (e.g. "airpods case") compete too, so a case that used to
be called "mug" gets called "airpods case" instead and isn't reported as an item.
"""
import logging
import os

import numpy as np
import yaml

log = logging.getLogger("nemo")

DEFAULT_MODEL = os.getenv("NEMO_MODEL", "yoloe-26s-seg.pt")


def pick_device():
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda:0"
        if torch.backends.mps.is_available():
            return "mps"   # Apple Silicon GPU
    except Exception:  # noqa: BLE001
        pass
    return "cpu"


def load_objects(path="objects.yaml"):
    """[{'name': 'TV remote', 'prompts': ['remote', 'remote control']}, ...] from the config file.

    `prompt` may be one wording or a list of them; the default is the object's name.
    """
    with open(path) as f:
        data = yaml.safe_load(f) or {}
    objects = []
    for o in data.get("objects") or []:
        if isinstance(o, str):
            o = {"name": o}
        name = str(o["name"]).strip()
        prompts = o.get("prompt") or name
        prompts = prompts if isinstance(prompts, list) else [prompts]
        objects.append({"name": name, "prompts": list(dict.fromkeys(str(p).strip().lower() for p in prompts))})
    if not objects:
        raise ValueError(f"No objects listed in {path}")
    return objects


def _unit(v):
    v = np.asarray(v, np.float32)
    return v / max(float(np.linalg.norm(v)), 1e-6)


class Detector:
    def __init__(self, model=DEFAULT_MODEL, device=None):
        from ultralytics import YOLOE
        self.device = device or pick_device()
        self.model_name = os.path.basename(model)
        log.info("Loading %s on %s (first run downloads it)...", model, self.device)
        self.model = YOLOE(model)
        self.entries = []          # one per class: {name, prompt, kind, learned}
        self._text_cache = {}

    def _text_embeddings(self, texts):
        missing = [t for t in dict.fromkeys(texts) if t not in self._text_cache]
        if missing:
            pe = self.model.model.get_text_pe(missing, cache_clip_model=True)
            for t, v in zip(missing, pe[0].float().cpu().numpy()):
                self._text_cache[t] = v
        return [self._text_cache[t] for t in texts]

    def set_objects(self, objects, learned=None):
        """Tell YOLOE what to look for.

        objects: from load_objects(). learned: {label: {"emb": vector, "object": name or None}}
        from nemo.learning. Items are reported by their object name; learned look-alikes
        (object None) are reported with kind "lookalike" so callers can ignore or show them.
        """
        entries, vectors = [], []
        texts = [(o["name"], p) for o in objects for p in o["prompts"]]
        seen = set()
        for (name, p), v in zip(texts, self._text_embeddings([p for _, p in texts])):
            if p in seen:
                continue
            seen.add(p)
            entries.append({"name": name, "prompt": p, "kind": "item", "learned": False})
            vectors.append(v)
        known = {o["name"] for o in objects}
        for label, info in (learned or {}).items():
            obj = info.get("object")
            if obj is not None and obj not in known:
                continue   # learned for an object that's no longer in objects.yaml
            entries.append({"name": obj or label, "prompt": f"{label} (learned)",
                            "kind": "item" if obj else "lookalike", "learned": True})
            vectors.append(_unit(info["emb"]))
        import torch
        param = next(self.model.model.parameters())
        pe = torch.from_numpy(np.stack(vectors)[None]).to(param.device, param.dtype)
        self.model.set_classes([e["prompt"] for e in entries], pe)
        self.entries = entries

    def detect(self, frame, conf=0.2, imgsz=640):
        """[{'name', 'prompt', 'kind', 'learned', 'conf', 'box': [x1, y1, x2, y2] in pixels}], best first."""
        try:
            res = self.model.predict(frame, conf=conf, imgsz=imgsz, device=self.device, verbose=False,
                                     agnostic_nms=False)[0]
        except Exception as e:  # noqa: BLE001 - some ops are missing on Apple's GPU; CPU always works
            if self.device == "cpu":
                raise
            log.warning("Detection failed on %s (%s); switching to the CPU", self.device, e)
            self.device = "cpu"
            return self.detect(frame, conf, imgsz)
        out = []
        if res.boxes is None:
            return out
        for box, c, k in zip(res.boxes.xyxy.cpu().numpy(), res.boxes.conf.cpu().numpy(),
                             res.boxes.cls.cpu().numpy()):
            e = self.entries[int(k)]
            out.append({**e, "conf": float(c), "box": [float(v) for v in box]})
        return sorted(out, key=lambda d: -d["conf"])

    def visual_embeddings(self, image, boxes, labels):
        """Fingerprints of labelled boxes in one photo: {label: vector}.

        boxes are [x1, y1, x2, y2] in pixels; boxes sharing a label are combined into one fingerprint.
        """
        if not boxes:
            return {}
        from ultralytics.models.yolo.yoloe import YOLOEVPDetectPredictor, YOLOEVPSegPredictor
        order = list(dict.fromkeys(labels))
        prompts = {"bboxes": np.array(boxes, dtype=np.float32),
                   "cls": np.array([order.index(lab) for lab in labels], dtype=np.int64)}
        m = self.model
        task = getattr(m.model, "task", "detect")
        pred = (YOLOEVPSegPredictor if task == "segment" else YOLOEVPDetectPredictor)(
            overrides={**m.overrides, "task": task, "mode": "predict", "save": False, "batch": 1,
                       "verbose": False, "device": self.device})
        pred.set_prompts(prompts)
        pred.setup_model(model=m.model, verbose=False)
        vpe = pred.get_vpe(image)[0].float().cpu().numpy()
        return {lab: _unit(vpe[j]) for j, lab in enumerate(order) if j < len(vpe)}

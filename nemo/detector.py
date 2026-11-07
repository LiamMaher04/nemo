"""Object detection with YOLOE: you give it plain-English prompts, it finds them in a photo.

YOLOE is "open-vocabulary": it isn't limited to a fixed list of classes, so new objects can be
added by name in objects.yaml. Later chunks add learning from our own labelled photos.
"""
import logging
import os

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


class Detector:
    def __init__(self, model=DEFAULT_MODEL, device=None):
        from ultralytics import YOLOE
        self.device = device or pick_device()
        log.info("Loading %s on %s (first run downloads it)...", model, self.device)
        self.model = YOLOE(model)
        self.names = []

    def set_objects(self, objects):
        """Tell YOLOE what to look for. Detections are reported with the object's name.

        Each wording becomes its own class. YOLOE-26 gives every box exactly one class, so an
        object's wordings compete and the best-fitting one wins; the box is still reported under
        the object's name, with the winning wording in 'prompt'.
        """
        prompts, self.names = [], []
        for o in objects:
            for p in o["prompts"]:
                if p not in prompts:
                    prompts.append(p)
                    self.names.append(o["name"])
        self.prompts = prompts
        pe = self.model.model.get_text_pe(prompts, cache_clip_model=True)
        self.model.set_classes(prompts, pe)

    def detect(self, frame, conf=0.2, imgsz=640):
        """[{'name', 'conf', 'box': [x1, y1, x2, y2] in pixels}], highest confidence first."""
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
            out.append({"name": self.names[int(k)], "prompt": self.prompts[int(k)], "conf": float(c),
                        "box": [float(v) for v in box]})
        return sorted(out, key=lambda d: -d["conf"])

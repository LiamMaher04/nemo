"""Chunk 1: live detection window. Shows what Nemo sees and what YOLOE finds, nothing else yet.

    python live.py                    # laptop webcam
    python live.py --source push      # wait for the device to send photos (see docs/interfaces.md)
    python live.py --conf 0.15        # find more (and more wrong) things

Keys in the window: Q quit, S save the current photo to backend/data/captures/ (for labelling later),
+/- change the confidence threshold.
"""
import argparse
import logging
import os
import time

import cv2

from vision.camera import open_source
from vision import BACKEND_DIR, OBJECTS_FILE, TEACH_DIR
from vision.detector import DEFAULT_CONF, Detector, load_objects
from vision.learning import Learned, TeachStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("nemo")

GREEN = (90, 220, 120)
ORANGE = (60, 160, 255)   # look-alikes: recognised, but not one of our items


def draw(frame, dets, lines):
    out = frame.copy()
    scale = max(0.5, frame.shape[1] / 1000)
    for d in dets:
        x1, y1, x2, y2 = (int(v) for v in d["box"])
        color = GREEN if d.get("kind", "item") == "item" else ORANGE
        cv2.rectangle(out, (x1, y1), (x2, y2), color, max(2, int(3 * scale)))
        text = f"{d['name']} {d['conf']:.2f}" + (f" ({d['prompt']})" if d["prompt"] != d["name"].lower() else "")
        (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.7 * scale, 2)
        ty = max(th + 8, y1)
        cv2.rectangle(out, (x1, ty - th - 8), (x1 + tw + 8, ty), color, -1)
        cv2.putText(out, text, (x1 + 4, ty - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.7 * scale, (20, 20, 20), 2, cv2.LINE_AA)
    for i, line in enumerate(lines):   # status lines, top-left
        y = int((24 + i * 26) * scale)
        cv2.putText(out, line, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6 * scale, (0, 0, 0), 4, cv2.LINE_AA)
        cv2.putText(out, line, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6 * scale, (255, 255, 255), 1, cv2.LINE_AA)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", default="webcam", help="webcam, webcam:N, push or push:PORT (push uses BACKEND_PORT from .env)")
    ap.add_argument("--objects", default=str(OBJECTS_FILE), help="what to look for")
    ap.add_argument("--conf", type=float, default=DEFAULT_CONF, help="minimum confidence to show a box (0 to 1); default DETECT_CONF in .env")
    ap.add_argument("--imgsz", type=int, default=640, help="detection size; 800+ finds small things like keys, slower")
    ap.add_argument("--device", default=None, help="cpu, mps or cuda:0 (default: automatic)")
    ap.add_argument("--no-window", action="store_true", help="print detections instead of showing a window")
    ap.add_argument("--teach-data", default=str(TEACH_DIR), help="use what teach.py learned (if it exists)")
    ap.add_argument("--no-learned", action="store_true", help="ignore what teach.py learned")
    args = ap.parse_args()

    objects = load_objects(args.objects)
    try:
        source = open_source(args.source)
    except (RuntimeError, ValueError) as e:
        raise SystemExit(f"\n{e}")
    detector = Detector(device=args.device)
    learned = None if args.no_learned else Learned.load(TeachStore(args.teach_data).learned_path, detector.model_name)
    detector.set_objects(objects, learned.for_detector() if learned else None)
    if learned and learned.data:
        log.info("Using what teach.py learned: %s", learned.summary())
    log.info("Looking for: %s", "; ".join(f"{o['name']} ({', '.join(o['prompts'])})" for o in objects))

    captures = BACKEND_DIR / "data" / "captures"
    captures.mkdir(parents=True, exist_ok=True)
    conf = args.conf
    frame, dets, ms, last = None, [], 0.0, 0.0
    try:
        while True:
            new = source.read()
            if new is not None:
                frame = new
                t0 = time.time()
                dets = detector.detect(frame, conf, args.imgsz)
                ms = (time.time() - t0) * 1000
                if args.no_window and time.time() - last > 1:
                    last = time.time()
                    found = ", ".join(f"{d['name']} {d['conf']:.2f}" for d in dets) or "nothing"
                    log.info("%s | %.0f ms | %s", source.status(), ms, found)
            elif args.no_window:
                time.sleep(0.05)
                continue

            if args.no_window:
                continue
            if frame is None:
                cv2.waitKey(100)
                continue
            lines = [source.status(), f"detect {ms:.0f} ms on {detector.device} | conf {conf:.2f}",
                     "Q quit  S save photo  +/- confidence"]
            cv2.imshow("Nemo: live detection", draw(frame, dets, lines))
            key = cv2.waitKey(1 if new is not None else 30) & 0xFF
            if key in (ord("q"), 27):
                break
            if key == ord("s"):
                path = str(captures / time.strftime("%Y%m%d-%H%M%S.jpg"))
                cv2.imwrite(path, frame)
                log.info("Saved %s", path)
            if key in (ord("+"), ord("=")):
                conf = min(0.9, conf + 0.05)
            if key in (ord("-"), ord("_")):
                conf = max(0.05, conf - 0.05)
    except KeyboardInterrupt:
        pass
    finally:
        source.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()

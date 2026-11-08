"""Try vision on the webcam or a folder of JPEGs. Run from the repo root:

    python -m backend.vision.run                  # webcam 0
    python -m backend.vision.run --camera 1       # another camera
    python -m backend.vision.run --folder path/   # every .jpg / .jpeg in a folder, in name order
    add --show to see the boxes (folder mode: press any key for the next image, q to quit)
"""

import argparse
import json
import time
from collections.abc import Iterator
from pathlib import Path

import cv2
import numpy as np

from backend.vision import detector, process
from backend.vision.pipeline import VisionResult

WINDOW = "Nemo vision"


def frames_from_folder(folder: Path) -> Iterator[bytes]:
    paths = sorted(p for p in folder.iterdir() if p.suffix.lower() in (".jpg", ".jpeg"))
    if not paths:
        raise SystemExit(f"No .jpg or .jpeg files in {folder}")
    for path in paths:
        yield path.read_bytes()


def frames_from_camera(index: int) -> Iterator[bytes]:
    cap = cv2.VideoCapture(index)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
    if not cap.isOpened():
        raise SystemExit(f"Could not open camera {index}")
    try:
        while True:
            ok, bgr = cap.read()
            if not ok:
                break
            ok, jpg = cv2.imencode(".jpg", bgr, [cv2.IMWRITE_JPEG_QUALITY, 90])
            if ok:
                yield jpg.tobytes()
    finally:
        cap.release()


def short(report: dict) -> str:
    """One line, with thumb_b64 shown as its length only."""
    shown = {k: (f"<{len(v)} chars>" if k == "thumb_b64" else v) for k, v in report.items()}
    return json.dumps(shown, separators=(", ", ": "))


def draw(jpeg_bytes: bytes, result: VisionResult) -> np.ndarray:
    img = cv2.imdecode(np.frombuffer(jpeg_bytes, np.uint8), cv2.IMREAD_COLOR)
    for name, (x, y, w, h), conf in result.furniture_boxes:
        cv2.rectangle(img, (x, y), (x + w, y + h), (255, 140, 0), 2)
        cv2.putText(img, f"{name} {conf:.2f}", (x + 4, y + 22), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 140, 0), 2)
    for s in result.sightings:
        x, y, w, h = json.loads(s["bbox_json"])
        colour = (0, 200, 0) if s["item_id"] else (0, 0, 255)  # red = ambiguous
        text = f"{s['item_id'] or '?'} {s['det_conf']:.2f} [{s['label']}]"
        cv2.rectangle(img, (x, y), (x + w, y + h), colour, 2)
        cv2.putText(img, text, (x, max(y - 6, 14)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, colour, 2)
    status = f"sharpness {result.sharpness:.0f}" + ("" if result.kept else f"  DROPPED: {result.drop_reason}")
    cv2.putText(img, status, (10, img.shape[0] - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
    scale = min(1.0, 1280 / img.shape[1])
    return cv2.resize(img, None, fx=scale, fy=scale) if scale < 1 else img


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Nemo vision on the webcam or a folder of JPEGs.")
    parser.add_argument("--folder", type=Path, help="folder of JPEGs (default: webcam)")
    parser.add_argument("--camera", type=int, default=0, help="webcam index (default 0)")
    parser.add_argument("--show", action="store_true", help="open a window with the boxes drawn")
    args = parser.parse_args()

    print(f"loading YOLOE on {detector.pick_device()} ...", flush=True)
    print(f"model ready in {detector.load():.1f}s", flush=True)

    source = frames_from_folder(args.folder) if args.folder else frames_from_camera(args.camera)
    frame_id = 0
    try:
        for jpeg_bytes in source:
            frame_id += 1
            ts_ms = time.time() * 1000  # UTC ms since epoch
            result = process(jpeg_bytes, frame_id, ts_ms)
            if result.kept:
                print(f"#{frame_id} sharpness {result.sharpness:.1f} KEPT "
                      f"{len(result.sightings)} sightings {result.ms:.0f} ms", flush=True)
                for s in result.sightings:
                    print(f"  sighting {short(s)}")
                print(f"  frame    {short(result.frame or {})}", flush=True)
            else:
                print(f"#{frame_id} sharpness {result.sharpness:.1f} DROPPED {result.drop_reason} "
                      f"{result.ms:.0f} ms", flush=True)
            if args.show:
                cv2.imshow(WINDOW, draw(jpeg_bytes, result))
                key = cv2.waitKey(0 if args.folder else 1) & 0xFF
                if key == ord("q"):
                    break
    except KeyboardInterrupt:
        pass
    finally:
        if args.show:
            cv2.destroyAllWindows()


if __name__ == "__main__":
    main()

"""Try vision on the webcam or a folder of JPEGs. Run from the repo root:

    python -m backend.vision.run                  # webcam 0
    python -m backend.vision.run --camera 1       # another camera
    python -m backend.vision.run --folder path/   # every .jpg / .jpeg in a folder, in name order
    python -m backend.vision.run --url http://<device-ip>/jpg   # poll a JPEG URL as fast as it answers
    add --show to see the boxes (folder mode: press any key for the next image, q to quit)
    add --save backend/vision/captures/ to keep every kept frame (faces blurred) as a JPEG
"""

import argparse
import http.client
import json
import subprocess
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path

import cv2
import numpy as np

from backend.vision import detector, pipeline, process, settings
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


def frames_from_url(url: str) -> Iterator[bytes]:
    """Fetch a JPEG from the URL again and again, as fast as it answers."""
    while True:
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                body = resp.read()
        except (urllib.error.URLError, http.client.HTTPException, TimeoutError, ConnectionError) as exc:
            print(f"fetch failed: {exc}; retrying in 1 s", flush=True)
            time.sleep(1)
            continue
        if not body.startswith(b"\xff\xd8"):
            print(f"not a JPEG ({len(body)} bytes); retrying in 1 s", flush=True)
            time.sleep(1)
            continue
        yield body


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
    if result.area and result.area.window:
        status += f"  area {result.area.area_id or '-'} {result.area.area_conf:.2f}"
    cv2.putText(img, status, (10, img.shape[0] - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
    scale = min(1.0, 1280 / img.shape[1])
    return cv2.resize(img, None, fx=scale, fy=scale) if scale < 1 else img


def check_save_dir(save_dir: Path) -> Path:
    """Create the --save folder. Inside the repo it must be gitignored (photos of our rooms)."""
    save_dir = save_dir.expanduser().resolve()
    if save_dir.is_relative_to(settings.REPO_ROOT):
        probe = save_dir / "probe.jpg"
        ignored = subprocess.run(["git", "-C", str(settings.REPO_ROOT), "check-ignore", "-q", str(probe)])
        if ignored.returncode != 0:
            raise SystemExit(f"{save_dir} is inside the repo but not gitignored. "
                             "Use e.g. backend/vision/captures/ (ignored) or a folder outside the repo.")
    save_dir.mkdir(parents=True, exist_ok=True)
    return save_dir


def save_frame(save_dir: Path, run_stamp: str, frame_id: int, jpeg_bytes: bytes) -> Path:
    """Save a kept frame, faces blurred first (nothing is stored with faces in it)."""
    bgr = cv2.imdecode(np.frombuffer(jpeg_bytes, np.uint8), cv2.IMREAD_COLOR)
    blurred = pipeline.blur_faces(bgr, cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY))
    path = save_dir / f"{run_stamp}_{frame_id:06d}.jpg"
    cv2.imwrite(str(path), blurred, [cv2.IMWRITE_JPEG_QUALITY, 95])
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Nemo vision on the webcam or a folder of JPEGs.")
    source_group = parser.add_mutually_exclusive_group()
    source_group.add_argument("--folder", type=Path, help="folder of JPEGs (default: webcam)")
    source_group.add_argument("--url", help="URL that returns one JPEG per request, e.g. http://<device-ip>/jpg")
    parser.add_argument("--camera", type=int, default=0, help="webcam index (default 0)")
    parser.add_argument("--show", action="store_true", help="open a window with the boxes drawn")
    parser.add_argument("--save", type=Path, metavar="DIR",
                        help="save every kept frame (faces blurred) as a JPEG in DIR; inside the repo DIR must be gitignored")
    args = parser.parse_args()
    save_dir = check_save_dir(args.save) if args.save else None
    run_stamp = time.strftime("%Y%m%d-%H%M%S")

    print(f"loading YOLOE and DINOv2 on {detector.pick_device()} ...", flush=True)
    pipeline.load()

    if args.folder:
        source = frames_from_folder(args.folder)
    elif args.url:
        source = frames_from_url(args.url)
    else:
        source = frames_from_camera(args.camera)
    frame_id = 0
    try:
        for jpeg_bytes in source:
            frame_id += 1
            ts_ms = time.time() * 1000  # UTC ms since epoch
            result = process(jpeg_bytes, frame_id, ts_ms)
            if result.kept:
                print(f"#{frame_id} sharpness {result.sharpness:.1f} KEPT {len(result.sightings)} sightings "
                      f"{result.ms:.0f} ms (YOLOE {result.yoloe_ms:.0f}, DINOv2 {result.dino_ms:.0f})", flush=True)
                if result.area and result.area.window:
                    a = result.area
                    print(f"  area     {a.area_id or '-'} conf {a.area_conf:.2f} over {a.window} frames | "
                          f"this frame: best {a.best} {a.best_sim:.3f}, next {a.next_sim:.3f}, vote {a.vote or 'none'}")
                for s in result.sightings:
                    print(f"  sighting {short(s)}")
                print(f"  frame    {short(result.frame or {})}", flush=True)
                if save_dir:
                    print(f"  saved    {save_frame(save_dir, run_stamp, frame_id, jpeg_bytes)}", flush=True)
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

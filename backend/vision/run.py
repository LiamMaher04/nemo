"""Try vision on the webcam or a folder of JPEGs. Run from the repo root:

    python -m backend.vision.run                  # webcam 0
    python -m backend.vision.run --camera 1       # another camera
    python -m backend.vision.run --folder path/   # every .jpg / .jpeg in a folder, in name order
    python -m backend.vision.run --url http://<device-ip>/jpg   # poll a JPEG URL
    add --fps N to change the webcam / --url frame rate (default 1, like Nemo; 0 = no limit)
    add --show to see the boxes (folder mode: press any key for the next image, q to quit)
    add --save backend/vision/captures/ to keep every kept frame (faces blurred) as a JPEG
    add --area couch to save every kept frame straight into REFS_DIR/areas/couch/ (references, no sorting)
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

from backend.vision import classes, detector, pipeline, process, settings
from backend.vision.pipeline import VisionResult

WINDOW = "Nemo vision"
CAMERA_START_S = 10.0  # how long a camera may take to send its first frame
CAMERA_DROPOUT_S = 5.0  # how long failed reads are retried once the camera has started


def frames_from_folder(folder: Path) -> Iterator[bytes]:
    paths = sorted(p for p in folder.iterdir() if p.suffix.lower() in (".jpg", ".jpeg"))
    if not paths:
        raise SystemExit(f"No .jpg or .jpeg files in {folder}")
    for path in paths:
        yield path.read_bytes()


def _open_camera(index: int) -> cv2.VideoCapture:
    cap = cv2.VideoCapture(index)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
    return cap


def frames_from_camera(index: int, fps: float) -> Iterator[bytes]:
    """Webcam frames, at most `fps` a second (0 = every frame).

    The camera is read continuously so each frame handed on is fresh, not one that sat in a
    buffer. A camera that is slow to start (an iPhone over Continuity Camera can take a second
    or two) gets CAMERA_START_S; after that, failed reads are retried for CAMERA_DROPOUT_S.
    """
    interval = 1.0 / fps if fps > 0 else 0.0
    cap = _open_camera(index)
    started = False
    failing_since: float | None = None
    deadline = time.monotonic() + CAMERA_START_S
    last_yield = 0.0
    try:
        while True:
            ok, bgr = cap.read() if cap.isOpened() else (False, None)
            now = time.monotonic()
            if not ok:
                if not started:
                    if now > deadline:
                        raise SystemExit(
                            f"Camera {index} sent no frames in {CAMERA_START_S:g} s. Check the --camera index "
                            "(the iPhone is often 0 or 1), that the iPhone is unlocked and nearby, and that "
                            "this terminal app has camera permission (System Settings > Privacy & Security > Camera).")
                elif failing_since is None:
                    failing_since = now
                    print(f"camera {index}: read failed, retrying for up to {CAMERA_DROPOUT_S:g} s", flush=True)
                elif now - failing_since > CAMERA_DROPOUT_S:
                    raise SystemExit(f"Camera {index} stopped sending frames for {CAMERA_DROPOUT_S:g} s; giving up.")
                if not cap.isOpened():  # some cameras only open once they are ready
                    cap.release()
                    cap = _open_camera(index)
                time.sleep(0.1)
                continue
            if not started:
                started = True
                print(f"camera {index}: first frame {bgr.shape[1]}x{bgr.shape[0]}", flush=True)
            if failing_since is not None:
                print(f"camera {index}: frames are back after {now - failing_since:.1f} s", flush=True)
                failing_since = None
            if now - last_yield < interval:
                continue  # read and dropped, to keep the next frame fresh
            last_yield = now
            ok, jpg = cv2.imencode(".jpg", bgr, [cv2.IMWRITE_JPEG_QUALITY, 90])
            if ok:
                yield jpg.tobytes()
    finally:
        cap.release()


def frames_from_url(url: str, fps: float) -> Iterator[bytes]:
    """Fetch a JPEG from the URL again and again, at most `fps` a second (0 = as fast as it answers)."""
    interval = 1.0 / fps if fps > 0 else 0.0
    last_fetch = 0.0
    while True:
        wait = last_fetch + interval - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        last_fetch = time.monotonic()
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
    for name, _, (x, y, w, h), conf in result.furniture_boxes:
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
        # Probe a JPEG and a JSON: a folder only covered by "*.jpg" would still commit the JSONs.
        probes = [str(save_dir / "probe.jpg"), str(save_dir / "probe.json")]
        out = subprocess.run(["git", "-C", str(settings.REPO_ROOT), "check-ignore", *probes],
                             capture_output=True, text=True).stdout  # one line per ignored path
        if len(out.splitlines()) != len(probes):
            raise SystemExit(f"{save_dir} is inside the repo but not gitignored. "
                             "Use e.g. backend/vision/captures/ (ignored) or a folder outside the repo.")
    save_dir.mkdir(parents=True, exist_ok=True)
    return save_dir


def save_frame(save_dir: Path, run_stamp: str, frame_id: int, jpeg_bytes: bytes,
               result: VisionResult, source: str, area_label: str | None) -> Path:
    """Save a kept frame (faces blurred, no boxes drawn) and, next to it, a JSON of what
    process() found in it. Returns the JPEG's path."""
    bgr = cv2.imdecode(np.frombuffer(jpeg_bytes, np.uint8), cv2.IMREAD_COLOR)
    blurred = pipeline.blur_faces(bgr, cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY))
    path = save_dir / f"{run_stamp}_{frame_id:06d}.jpg"
    cv2.imwrite(str(path), blurred, [cv2.IMWRITE_JPEG_QUALITY, 95])
    detections = frame_json(path.name, bgr.shape, result, source, area_label)
    write_json_atomic(path.with_suffix(".json"), detections)
    return path


def frame_json(image: str, shape: tuple[int, ...], result: VisionResult, source: str,
               area_label: str | None) -> dict:
    """Everything process() found in one kept frame (format in README.md)."""
    a = result.area
    frame = result.frame or {}
    items = []
    for i, (s, how) in enumerate(zip(result.sightings, result.matched_by)):
        items.append({
            "det": i,
            "item_id": s["item_id"],
            "label": s["label"],
            "det_conf": s["det_conf"],
            "candidates": json.loads(s["candidates_json"]),
            "match_margin": s["match_margin"],
            "matched_by": how,
            "furniture": s["furniture"],
            "rel_pos": json.loads(s["rel_pos_json"]),
            "bbox": json.loads(s["bbox_json"]),
        })
    return {
        "version": 1,
        "image": image,
        "frame_id": frame.get("frame_id"),
        "ts_ms": frame.get("ts_ms"),
        "width": shape[1],
        "height": shape[0],
        "source": source,
        "sharpness": round(result.sharpness, 2),
        "area": {
            "area_id": frame.get("area_id", ""),
            "area_conf": frame.get("area_conf", 0.0),
            "vote": a.vote if a else "",
            "best": a.best if a else "",
            "best_sim": round(a.best_sim, 4) if a else 0.0,
            "next_sim": round(a.next_sim, 4) if a else 0.0,
            "window": a.window if a else 0,
        },
        "area_label": area_label,
        "items": items,
        "furniture": [{"name": n, "label": w, "conf": c, "bbox": b} for n, w, b, c in result.furniture_boxes],
        "settings": {
            "DETECT_IMGSZ": settings.DETECT_IMGSZ,
            "DETECT_CONF": settings.DETECT_CONF,
            "SHARPNESS_GATE": settings.SHARPNESS_GATE,
            "ITEM_SIM_MIN": settings.ITEM_SIM_MIN,
            "ITEM_MARGIN_MIN": settings.ITEM_MARGIN_MIN,
            "AREA_SIM_MIN": settings.AREA_SIM_MIN,
            "AREA_MARGIN_MIN": settings.AREA_MARGIN_MIN,
            "AREA_VOTE_S": settings.AREA_VOTE_S,
            "AREA_VOTE_MIN": settings.AREA_VOTE_MIN,
        },
    }


def write_json_atomic(path: Path, data: dict) -> None:
    """Write to a temporary file, then rename, so a crash never leaves half a file."""
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=1))
    tmp.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Nemo vision on the webcam or a folder of JPEGs.")
    source_group = parser.add_mutually_exclusive_group()
    source_group.add_argument("--folder", type=Path, help="folder of JPEGs (default: webcam)")
    source_group.add_argument("--url", help="URL that returns one JPEG per request, e.g. http://<device-ip>/jpg")
    parser.add_argument("--camera", type=int, default=0, help="webcam index (default 0)")
    parser.add_argument("--fps", type=float, default=1.0,
                        help="max frames a second from the webcam or --url (default 1, like Nemo; 0 = no limit); "
                             "ignored for --folder")
    parser.add_argument("--show", action="store_true", help="open a window with the boxes drawn")
    parser.add_argument("--save", type=Path, metavar="DIR",
                        help="save every kept frame (faces blurred) as a JPEG in DIR; inside the repo DIR must be gitignored")
    parser.add_argument("--area", metavar="NAME",
                        help="label this capture as area NAME: kept frames are saved straight into "
                             "REFS_DIR/areas/NAME/ (or into --save DIR if given)")
    args = parser.parse_args()
    if args.area:
        note = "" if args.area in classes.AREA_IDS else " (test only, not a seed area_id)"
        if not args.save:
            args.save = settings.REFS_DIR / "areas" / args.area
        print(f"area label: {args.area}{note}; kept frames go to {args.save}", flush=True)
    save_dir = check_save_dir(args.save) if args.save else None
    run_stamp = time.strftime("%Y%m%d-%H%M%S")

    print(f"loading YOLOE and DINOv2 on {detector.pick_device()} ...", flush=True)
    pipeline.load()

    limit = f"{args.fps:g} fps" if args.fps > 0 else "no limit"
    if args.folder:
        print(f"source: folder {args.folder} (--fps ignored, every image is used)", flush=True)
        source = frames_from_folder(args.folder)
        source_name = f"folder {args.folder}"
    elif args.url:
        print(f"source: {args.url}, frame rate limit {limit}", flush=True)
        source = frames_from_url(args.url, args.fps)
        source_name = args.url
    else:
        print(f"source: camera {args.camera}, frame rate limit {limit}", flush=True)
        source = frames_from_camera(args.camera, args.fps)
        source_name = f"camera {args.camera}"
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
                    saved = save_frame(save_dir, run_stamp, frame_id, jpeg_bytes, result, source_name, args.area)
                    print(f"  saved    {saved} (+ .json)", flush=True)
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

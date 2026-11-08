"""Review saved frames in a local page. Run from the repo root:

    python -m backend.vision.review backend/vision/captures/

then open http://127.0.0.1:8765. The page only ever listens on 127.0.0.1: photos of our rooms
never leave the laptop. Verdicts and comments go to review.json in the same folder as you go.
"""

import argparse
import json
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import cv2

from backend.vision import classes, settings
from backend.vision.pipeline import ITEM_CROP_PAD, _crop
from backend.vision.run import require_gitignored, write_json_atomic

HOST = "127.0.0.1"  # never anything else
PAGE = Path(__file__).with_name("review.html")


class Review:
    """The folder being reviewed: its frames (JPEG + JSON pairs) and review.json."""

    def __init__(self, folder: Path) -> None:
        self.folder = folder
        self.path = folder / "review.json"
        self.lock = threading.Lock()
        self.frames: dict[str, dict] = {}  # stem -> detections JSON, in time order
        for js in sorted(folder.glob("*.json")):
            if js.name != "review.json" and js.with_suffix(".jpg").exists():
                self.frames[js.stem] = json.loads(js.read_text())
        self.data = json.loads(self.path.read_text()) if self.path.exists() else {
            "version": 1, "frames": {}, "refs_added": []}

    def save(self) -> None:
        write_json_atomic(self.path, self.data)

    def set_frame(self, stem: str, record: dict) -> None:
        """Replace one frame's verdicts, missed items and comment."""
        detections = {str(k): v for k, v in record.get("detections", {}).items() if v in ("correct", "wrong")}
        missed = sorted({m for m in record.get("missed", []) if m in classes.ITEMS})
        with self.lock:
            self.data["frames"][stem] = {
                "detections": detections,
                "missed": missed,
                "comment": str(record.get("comment", ""))[:2000],
                "updated_ts_ms": time.time() * 1000,
            }
            self.save()

    def add_item_ref(self, stem: str, det: int, item_id: str) -> str:
        """Save a detection's crop (10% padding, like DINOv2's live crops) as a reference."""
        bbox = self.frames[stem]["items"][det]["bbox"]
        x, y, w, h = bbox
        img = cv2.imread(str(self.folder / f"{stem}.jpg"), cv2.IMREAD_COLOR)
        crop = _crop(img, (x, y, x + w, y + h), ITEM_CROP_PAD)
        out_dir = settings.REFS_DIR / "items" / item_id
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / f"{stem}_d{det}.jpg"
        cv2.imwrite(str(out), crop, [cv2.IMWRITE_JPEG_QUALITY, 95])
        with self.lock:
            self.data["refs_added"].append({"kind": "item", "id": item_id, "from": stem, "det": det,
                                            "path": str(out.relative_to(settings.REPO_ROOT)
                                                        if out.is_relative_to(settings.REPO_ROOT) else out)})
            self.save()
        return str(out)


def make_handler(review: Review, port: int) -> type[BaseHTTPRequestHandler]:
    allowed_hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
    allowed_origins = {f"http://{h}" for h in allowed_hosts}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: object) -> None:
            pass  # quiet

        def _send(self, status: int, body: bytes, ctype: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, status: int, data: object) -> None:
            self._send(status, json.dumps(data).encode(), "application/json")

        def _host_ok(self) -> bool:
            # Only our own address: stops other sites reaching us through a renamed address.
            if self.headers.get("Host") not in allowed_hosts:
                self._json(HTTPStatus.FORBIDDEN, {"error": "bad host"})
                return False
            return True

        def do_GET(self) -> None:
            if not self._host_ok():
                return
            if self.path == "/":
                self._send(HTTPStatus.OK, PAGE.read_bytes(), "text/html; charset=utf-8")
            elif self.path == "/api/frames":
                self._json(HTTPStatus.OK, {"frames": [{"stem": s, **f} for s, f in review.frames.items()],
                                           "review": review.data, "item_ids": list(classes.ITEMS)})
            elif self.path.startswith("/img/"):
                stem = self.path[len("/img/"):]
                if stem not in review.frames:  # only frames in the index, never a path
                    self._json(HTTPStatus.NOT_FOUND, {"error": "no such frame"})
                    return
                self._send(HTTPStatus.OK, (review.folder / f"{stem}.jpg").read_bytes(), "image/jpeg")
            else:
                self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})

        def do_POST(self) -> None:
            if not self._host_ok():
                return
            # JSON only, and from our own page only: a JSON content type makes the browser ask
            # first (and we never answer) for any other site, and Origin must be ours if sent.
            origin = self.headers.get("Origin")
            if self.headers.get("Content-Type") != "application/json" or (origin and origin not in allowed_origins):
                self._json(HTTPStatus.FORBIDDEN, {"error": "bad request origin"})
                return
            try:
                body = json.loads(self.rfile.read(min(int(self.headers.get("Content-Length", 0)), 100_000)))
                stem = body["stem"]
                if stem not in review.frames:
                    raise KeyError(stem)
                if self.path == "/api/review":
                    review.set_frame(stem, body)
                    self._json(HTTPStatus.OK, {"ok": True})
                elif self.path == "/api/ref_item":
                    det, item_id = int(body["det"]), body["item_id"]
                    if item_id not in classes.ITEMS or not 0 <= det < len(review.frames[stem]["items"]):
                        raise ValueError("bad item_id or detection")
                    self._json(HTTPStatus.OK, {"ok": True, "path": review.add_item_ref(stem, det, item_id)})
                else:
                    self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})
            except (KeyError, ValueError, TypeError, json.JSONDecodeError) as exc:
                self._json(HTTPStatus.BAD_REQUEST, {"error": f"bad request: {exc}"})

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser(description="Review saved Nemo frames on a local page.")
    parser.add_argument("folder", type=Path, help="folder of frames saved with run.py --save (or --area)")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    folder = require_gitignored(args.folder)  # review.json is written here
    require_gitignored(settings.REFS_DIR / "items")  # reference crops are written here
    if not folder.is_dir():
        raise SystemExit(f"No folder {folder}")
    review = Review(folder)
    if not review.frames:
        raise SystemExit(f"No saved frames (JPEG + JSON pairs) in {folder}")
    server = ThreadingHTTPServer((HOST, args.port), make_handler(review, args.port))
    print(f"{len(review.frames)} frames in {folder}")
    print(f"open http://{HOST}:{args.port}  (Ctrl-C to stop; verdicts are saved as you go)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()

"""Where frames come from: the laptop webcam (for testing) or the device pushing photos over Wi-Fi.

Both look the same to the rest of Nemo: `source.read()` returns the newest frame (a BGR numpy
array) or None if there isn't one yet.

    open_source("webcam")      laptop camera 0
    open_source("webcam:1")    another camera (e.g. an iPhone via Continuity Camera)
    open_source("push")        wait for the device to POST photos to http://<laptop-ip>:<BACKEND_PORT>/frame
    open_source("push:9000")   same, on another port (use this if the FastAPI backend is already on 8000)

The push protocol the device's firmware must follow is in docs/interfaces.md.
"""
import json
import logging
import os
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import cv2
import numpy as np

log = logging.getLogger("nemo")

MAX_FRAME_BYTES = 2_000_000   # a VGA JPEG is ~30-60 KB; anything this big is a mistake


class WebcamSource:
    """The laptop's own camera. Good for testing everything without the board."""

    def __init__(self, index=0):
        self.name = f"webcam {index}"
        self.cap = cv2.VideoCapture(index)
        if not self.cap.isOpened():
            raise RuntimeError(
                f"Couldn't open camera {index}. On a Mac, allow Terminal (or your editor) under "
                "System Settings > Privacy & Security > Camera, then try again.")
        self.frames = 0

    def read(self):
        ok, frame = self.cap.read()
        if not ok:
            return None
        self.frames += 1
        return frame

    def status(self):
        return f"{self.name}"

    def close(self):
        self.cap.release()


class PushSource:
    """A tiny HTTP server that the device sends photos to. Keeps only the newest photo."""

    def __init__(self, port=None):
        port = port or int(os.getenv("BACKEND_PORT") or 8000)
        self.port = port
        self.name = f"device (push, port {port})"
        self._lock = threading.Lock()
        self._frame = None
        self._fresh = False
        self.frames = 0
        self.last_at = None        # time the newest photo arrived
        self.last_from = None      # the device's IP address
        self.last_device = None    # X-Device-Id header, e.g. "nemo-a"
        self.last_bytes = 0
        self._intervals = []       # seconds between photos, for the frame-rate readout
        try:
            self.server = ThreadingHTTPServer(("0.0.0.0", port), self._handler())
        except OSError as e:
            raise RuntimeError(f"Port {port} is busy (is another live.py still running?). "
                               f"Close it, or use --source push:{port + 1}.") from e
        self.server.daemon_threads = True
        threading.Thread(target=self.server.serve_forever, daemon=True, name="push-server").start()
        log.info("Waiting for the device to send photos to http://%s:%d/frame", local_ip(), port)

    def _handler(self):
        source = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):   # keep the terminal quiet
                pass

            def _reply(self, code, body):
                data = json.dumps(body).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                if self.path.split("?")[0] == "/ping":
                    self._reply(200, {"ok": True, "service": "nemo"})
                else:
                    self._reply(404, {"ok": False, "error": "try POST /frame or GET /ping"})

            def do_POST(self):
                if self.path.split("?")[0] != "/frame":
                    self._reply(404, {"ok": False, "error": "POST photos to /frame"})
                    return
                length = int(self.headers.get("Content-Length") or 0)
                if not 0 < length <= MAX_FRAME_BYTES:
                    self._reply(400, {"ok": False, "error": f"bad Content-Length {length}"})
                    return
                data = self.rfile.read(length)
                frame = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
                if frame is None:
                    self._reply(400, {"ok": False, "error": "body isn't a JPEG I can read"})
                    return
                source._store(frame, self.headers.get("X-Device-Id") or self.client_address[0], length)
                self._reply(200, {"ok": True})

        return Handler

    def _store(self, frame, sender, nbytes):
        now = time.time()
        with self._lock:
            if self.last_at is not None:
                self._intervals = (self._intervals + [now - self.last_at])[-10:]
            self._frame, self._fresh = frame, True
            self.frames += 1
            self.last_at, self.last_from, self.last_bytes = now, sender, nbytes

    def read(self):
        """The newest photo, or None if nothing new has arrived since the last read."""
        with self._lock:
            if not self._fresh:
                return None
            self._fresh = False
            return self._frame

    def fps(self):
        with self._lock:
            iv = self._intervals
            return len(iv) / sum(iv) if iv and sum(iv) > 0 else 0.0

    def status(self):
        if self.last_at is None:
            return f"waiting for the device on http://{local_ip()}:{self.port}/frame"
        age = time.time() - self.last_at
        return (f"device {self.last_from}: {self.fps():.1f} photos/s, {self.last_bytes // 1024} KB each, "
                f"last {age:.1f}s ago")

    def close(self):
        self.server.shutdown()


def open_source(spec="webcam"):
    kind, _, arg = spec.partition(":")
    if kind == "webcam":
        return WebcamSource(int(arg or 0))
    if kind == "push":
        return PushSource(int(arg) if arg else None)
    raise ValueError(f"Unknown source '{spec}'. Use webcam, webcam:N, push or push:PORT.")


def local_ip():
    """This laptop's address on the current network (what the device should send to)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))   # no packet is sent; this just picks the right interface
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"

"""Grab frames from Nemo's camera for reference photos, keeping only the useful ones.

Run from C:\\HackUTD\\Nemo with the venv on:
    backend\\.venv\\Scripts\\python.exe grab.py desk
    backend\\.venv\\Scripts\\python.exe grab.py desk --url http://172.20.10.9/jpg

What it does for you, so there's nothing to delete afterwards:
  - skips blurry frames (sharpness below --sharp, default 40)
  - skips near-duplicates of the last saved frame (standing still saves nothing new)
  - saves at most --max-per-sec frames a second (default 2)
  - shows a live window with what it's doing

While it runs (in the preview window):
  P        pause / resume saving (walk to the next spot with it paused)
  Space    save this frame even if it would be skipped
  Q / Esc  quit
In the terminal: type a new area name and press Enter to switch folders without restarting
(e.g. type "sitting_area" + Enter). Type "items" for the walk-around item capture.

Frames go to captures/grab/<area>/ (captures/ is gitignored, so nothing reaches GitHub).
"""
from __future__ import annotations

import argparse
import os
import sys
import threading
import time

import cv2
import numpy as np
import requests

p = argparse.ArgumentParser()
p.add_argument("area", nargs="?", default="raw")
p.add_argument("--url", default=os.getenv("NEMO_JPG_URL", "http://172.20.10.9/jpg"))
p.add_argument("--sharp", type=float, default=40.0, help="skip frames less sharp than this")
p.add_argument("--dup", type=float, default=2.0, help="skip frames this similar to the last saved one")
p.add_argument("--max-per-sec", type=float, default=2.0)
p.add_argument("--no-window", action="store_true", help="don't open the preview window")
args = p.parse_args()

state = {"area": args.area, "paused": False, "quit": False}
counts: dict[str, int] = {}


def folder(area: str) -> str:
    out = os.path.join("captures", "grab", area)
    os.makedirs(out, exist_ok=True)
    return out


def read_terminal() -> None:
    for line in sys.stdin:
        name = line.strip().replace(" ", "_")
        if name:
            state["area"] = name
            folder(name)
            print(f"\n>>> now saving to captures/grab/{name}/")


threading.Thread(target=read_terminal, daemon=True).start()
folder(state["area"])
print(f"Grabbing from {args.url}\nSaving to captures/grab/{state['area']}/  "
      "(P pause, Space force save, Q quit; type a new area name + Enter to switch)")

session = requests.Session()
last_thumb = None
last_save = 0.0
fails = 0

while not state["quit"]:
    try:
        r = session.get(args.url, timeout=3)
        data = r.content
        if not (r.ok and data[:2] == b"\xff\xd8"):
            raise ValueError("not a JPEG")
        img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("cut-short frame")
        fails = 0
    except Exception as e:
        fails += 1
        if fails in (1, 10) or fails % 50 == 0:
            print(f"(can't get a frame: {e}; retrying)")
        time.sleep(0.5)
        continue

    grey = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    sharp = cv2.Laplacian(grey, cv2.CV_64F).var()
    thumb = cv2.resize(grey, (64, 48)).astype(np.float32)
    diff = 999.0 if last_thumb is None else float(np.abs(thumb - last_thumb).mean())
    now = time.time()

    force = False
    key = -1
    if not args.no_window:
        view = img.copy()
        area = state["area"]
        status = "PAUSED" if state["paused"] else ("BLURRY" if sharp < args.sharp else
                                                   "SAME" if diff < args.dup else "ok")
        colour = (0, 200, 255) if status != "ok" else (0, 220, 0)
        cv2.putText(view, f"{area}  saved {counts.get(area, 0)}  sharp {sharp:.0f}  {status}",
                    (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, colour, 2)
        cv2.imshow("Nemo grab", view)
        key = cv2.waitKey(1) & 0xFF
        if key in (ord("q"), 27):
            break
        if key == ord("p"):
            state["paused"] = not state["paused"]
            print("paused" if state["paused"] else "saving again")
        if key == ord(" "):
            force = True

    if state["paused"] and not force:
        continue
    if not force:
        if sharp < args.sharp or diff < args.dup or now - last_save < 1.0 / args.max_per_sec:
            continue

    area = state["area"]
    path = os.path.join(folder(area), f"{int(now * 1000)}.jpg")
    with open(path, "wb") as f:
        f.write(data)
    counts[area] = counts.get(area, 0) + 1
    last_thumb, last_save = thumb, now
    if counts[area] % 5 == 0:
        print(f"{area}: {counts[area]} saved")

cv2.destroyAllWindows()
print("\nDone. Saved:", ", ".join(f"{a} {n}" for a, n in counts.items()) or "nothing")

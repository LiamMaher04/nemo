"""Show the possible-fall alert end to end, for the video.

Run from the repo root, with the venv:

    backend\\.venv\\Scripts\\python.exe -m backend.demo_fall           # through the running backend
    backend\\.venv\\Scripts\\python.exe -m backend.demo_fall --here    # no backend needed, a few seconds

Default: posts a dark frame (what Nemo sees lying face down) to the backend's POST /frame once a
second for FALL_WINDOW_S + 10 s. The backend's own fall check (backend/fall.py) notices, asks
Super VL, and Spacetime's report_possible_fall raises the carer alert. Takes about a minute.
If the backend is also pulling real frames from Nemo, cover Nemo's camera too, or a real frame
ends the streak.

--here: calls the same fall.observe() in this process with a fake clock (one frame a second),
then waits for the Super VL check. Same function, same Super VL question, same reducer.

Either way the alert is a normal carer alert: with CARER_ALERTS=off it's recorded but not texted.
At most one possible_fall alert every 30 minutes, so a second run soon after adds nothing.
"""

import argparse
import sys
import time

import cv2
import httpx
import numpy as np

from backend import settings
from backend import spacetime_client as st

BACKEND = f"http://127.0.0.1:{settings.BACKEND_PORT}"


def dark_frame(seed: int) -> bytes:
    """A 1024x768 frame that's almost black with a little sensor noise, like a camera face down."""
    rng = np.random.default_rng(seed)
    img = rng.normal(8, 3, (768, 1024, 3)).clip(0, 255).astype(np.uint8)
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])
    assert ok
    return buf.tobytes()


def fall_alerts() -> list[dict]:
    return sorted((r for r in st.sql("SELECT * FROM alerts") if r["type"] == "possible_fall"), key=lambda r: r["id"])


def show_new(before: set[int], wait_s: float) -> None:
    deadline = time.time() + wait_s
    while time.time() < deadline:
        new = [r for r in fall_alerts() if int(r["id"]) not in before]
        if new:
            for r in new:
                print(f"possible_fall alert #{r['id']} (channel {r['channel']}, sent {r['sent']}): {r['message']!r}")
            return
        time.sleep(1)
    print("No new possible_fall alert. Either Super VL said no, or one was already raised in the last 30 minutes.")


def via_backend() -> None:
    try:
        httpx.get(f"{BACKEND}/health", timeout=3)
    except Exception:
        sys.exit(f"The backend isn't running at {BACKEND}. Start it, or use --here.")
    before = {int(r["id"]) for r in fall_alerts()}
    seconds = int(settings.FALL_WINDOW_S) + 10
    print(f"Posting {seconds} dark frames to {BACKEND}/frame, one a second (FALL_WINDOW_S = {settings.FALL_WINDOW_S:g})...")
    for i in range(seconds):
        started = time.time()
        httpx.post(f"{BACKEND}/frame", content=dark_frame(i), headers={"Content-Type": "image/jpeg",
                                                                       "X-Device-Id": "demo_fall"}, timeout=10)
        if i % 10 == 0:
            print(f"  {i} s")
        time.sleep(max(0.0, 1.0 - (time.time() - started)))
    show_new(before, wait_s=30)


def here() -> None:
    from backend import fall, vl
    before = {int(r["id"]) for r in fall_alerts()}
    t0 = time.time()
    seconds = int(settings.FALL_WINDOW_S) + 2
    result = ""
    for i in range(seconds):
        result = fall.observe(dark_frame(i), now_s=t0 + i)  # fake clock: one frame a second
        if result == "asked":
            print(f"After {i} s of dark frames the fall check asked Super VL.")
            break
    if result != "asked":
        sys.exit(f"The fall check never asked Super VL (last result: {result}). Is FALL_CHECK on?")
    vl._jobs.join()  # wait for the Super VL question and the reducer call
    show_new(before, wait_s=10)


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--here", action="store_true", help="run the fall check in this process, no backend needed")
    args = parser.parse_args()
    here() if args.here else via_backend()

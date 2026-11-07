"""Pretend to be the Nemo device: push photos to Nemo exactly the way the firmware should.

Use it to test the laptop side before the board works, or to compare against the real board.

    python tools/fake_board.py                      # webcam photos to http://localhost:8000/frame
    python tools/fake_board.py --image photo.jpg    # send the same photo over and over
    python tools/fake_board.py --url http://192.168.1.20:8000 --fps 1

Follows docs/interfaces.md (POST /frame). Uses only the standard library plus OpenCV.
"""
import argparse
import http.client
import time
import urllib.parse

import cv2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8000", help="where Nemo is listening")
    ap.add_argument("--image", help="send this file instead of webcam photos")
    ap.add_argument("--fps", type=float, default=1.0, help="photos per second")
    ap.add_argument("--width", type=int, default=1280, help="resize to this width (docs/interfaces.md: 1280+)")
    ap.add_argument("--device-id", default="nemo-test", help="sent as X-Device-Id")
    ap.add_argument("--quality", type=int, default=80, help="JPEG quality 0-100")
    args = ap.parse_args()

    u = urllib.parse.urlparse(args.url)
    conn = http.client.HTTPConnection(u.hostname, u.port or 80, timeout=5)   # one connection, reused
    cam = None if args.image else cv2.VideoCapture(0)
    still = cv2.imread(args.image) if args.image else None
    if args.image and still is None:
        raise SystemExit(f"Can't read {args.image}")

    sent = 0
    started = time.time()
    while True:
        t0 = time.time()
        frame = still if still is not None else cam.read()[1]
        if frame is None:
            raise SystemExit("No webcam photo. Check camera permissions, or use --image.")
        if frame.shape[1] > args.width:
            frame = cv2.resize(frame, (args.width, int(frame.shape[0] * args.width / frame.shape[1])))
        jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, args.quality])[1].tobytes()
        try:
            conn.request("POST", "/frame", body=jpeg, headers={
                "Content-Type": "image/jpeg", "X-Device-Id": args.device_id,
                "X-Frame-Ts": str(int((time.time() - started) * 1000))})
            resp = conn.getresponse()
            resp.read()
            sent += 1
            print(f"\rsent {sent} photos, {len(jpeg) // 1024} KB, reply {resp.status}, "
                  f"{(time.time() - t0) * 1000:.0f} ms", end="", flush=True)
        except (OSError, http.client.HTTPException) as e:
            print(f"\nCouldn't reach {args.url}: {e}. Is live.py --source push running?")
            conn.close()
            time.sleep(2)
        time.sleep(max(0.0, 1 / args.fps - (time.time() - t0)))


if __name__ == "__main__":
    main()

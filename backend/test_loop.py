"""End-to-end test: JPEGs -> POST /frame -> vision -> Spacetime -> "where's my remote?".

Put photos in captures/test_frames/ (gitignored), named so they sort in the order taken. Then:
    backend\\.venv\\Scripts\\python.exe -m backend.test_loop
    backend\\.venv\\Scripts\\python.exe -m backend.test_loop --folder some/other/folder --loops 2
WARNING: calls reset_memory first. Items and areas are kept.
"""

import argparse
import time
from pathlib import Path

from fastapi.testclient import TestClient

from backend import frames, seed_spacetime, settings
from backend import spacetime_client as st
from backend.main import app


def wait_idle(timeout_s: float = 600) -> None:
    """Wait until vision has loaded and no frame is being processed."""
    deadline = time.time() + timeout_s
    time.sleep(0.5)
    while (frames._busy.locked() or frames._next_frame_id == 0) and time.time() < deadline:
        time.sleep(0.2)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--folder", type=Path, default=settings.CAPTURES_DIR / "test_frames")
    parser.add_argument("--loops", type=int, default=1, help="send the folder this many times")
    args = parser.parse_args()

    photos = sorted(p for p in args.folder.glob("*") if p.suffix.lower() in (".jpg", ".jpeg"))
    if not photos:
        raise SystemExit(f"No .jpg/.jpeg photos in {args.folder}")

    st.call("reset_memory")
    seed_spacetime.main()

    with TestClient(app) as client:
        print("loading vision ...")
        wait_idle()
        print(f"sending {len(photos)} photos x {args.loops} to /frame, one a second")
        for _ in range(args.loops):
            for path in photos:
                started = time.monotonic()
                r = client.post("/frame", content=path.read_bytes(),
                                headers={"Content-Type": "image/jpeg", "X-Device-Id": "nemo-test"})
                skipped = " (skipped: busy)" if r.json().get("skipped") else ""
                print(f"  POST {path.name}: {r.status_code}{skipped}")
                time.sleep(max(0.0, 1.0 - (time.monotonic() - started)))
        wait_idle()

        h = client.get("/health").json()["vision"]
        print(f"\n/health vision: {h}")
        kept = [x for x in frames.history if x["kept"]]
        steady = kept[1:]  # ignore the first kept frame (warm-up)
        if steady:
            v = sum(x["vision_ms"] for x in steady) / len(steady)
            s = sum(x["spacetime_ms"] for x in steady) / len(steady)
            print(f"steady state over {len(steady)} kept frames (first ignored): "
                  f"vision {v:.0f} ms, spacetime {s:.0f} ms per frame")
        print(f"frames saved in {settings.FRAMES_DIR}: {len(list(settings.FRAMES_DIR.glob('*.jpg')))}")

        print("\nitem_state:")
        for row in st.sql("SELECT * FROM item_state"):
            print(f"  {row['item_id']:<16} state={row['state']} area={row['area_id']!r} furniture={row['furniture']!r} "
                  f"rel_pos={row['rel_pos_json']} conf={row['confidence']:.2f}")
        remote = st.sql("SELECT * FROM item_state WHERE item_id = 'tv_remote'")
        if not remote:
            print("  (tv_remote not in item_state: it needs 2 sightings in a row on the same furniture)")

        r = client.post("/ask_text", json={"question": "where's my remote?"})
        body = r.json()
        print(f"\nQ: where's my remote?\nA: {body.get('answer', body)}")
        for tc in body.get("tool_calls", []):
            print(f"   tool {tc['name']}({tc['args']})")


if __name__ == "__main__":
    main()

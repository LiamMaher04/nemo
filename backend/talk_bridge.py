"""Laptop stand-in for Nemo's button: hold SPACE, ask out loud, hear the answer on Nemo.

Until Laura's firmware button POSTs to /ask itself, this does the round trip:
  hold SPACE   -> GET  {NEMO_URL}/rec/start          (Nemo's mic starts recording)
  release      -> GET  {NEMO_URL}/rec/stop           (16 kHz mono 16-bit WAV back)
               -> POST http://127.0.0.1:{BACKEND_PORT}/ask   (speech to text, agent, speech)
               -> POST {NEMO_URL}/play  (multipart "file")   (Nemo speaks the answer)
ESC quits. Any error prints one line and it keeps running.

Needs the backend running (python -m backend.main) and NEMO_URL in .env. Run from the repo root:
    backend\\.venv\\Scripts\\python.exe -m backend.talk_bridge
macOS: allow the terminal under Privacy & Security > Accessibility, or SPACE won't be seen.
"""

import socket
import threading
import time
from urllib.parse import unquote

import requests
from pynput import keyboard

from backend import settings

ASK_URL = f"http://127.0.0.1:{settings.BACKEND_PORT}/ask"
# Only one talk_bridge may run: two would each hear SPACE, and every answer would be spoken twice.
# Holding this local port is the lock; the OS frees it when the process ends, even on a crash.
SINGLE_INSTANCE_PORT = 47613
QUESTION_WAV = settings.CAPTURES_DIR / "talk_question.wav"
ANSWER_WAV = settings.CAPTURES_DIR / "talk_answer.wav"

_recording = False
_rec_started = 0.0
_busy = threading.Lock()  # one question at a time


def _start() -> None:
    global _recording, _rec_started
    try:
        requests.get(f"{settings.NEMO_URL}/rec/start", timeout=3).raise_for_status()
        _recording = True
        _rec_started = time.perf_counter()
        print("recording... (release SPACE to stop)", flush=True)
    except Exception as exc:
        print(f"could not start recording on Nemo: {exc}", flush=True)


def _round_trip() -> None:
    """Stop recording, ask the backend, play the answer on Nemo."""
    if not _busy.acquire(blocking=False):
        print("still answering the last question, try again in a moment", flush=True)
        return
    try:
        t0 = time.perf_counter()
        r = requests.get(f"{settings.NEMO_URL}/rec/stop", timeout=20)
        r.raise_for_status()
        wav = r.content
        held_s = t0 - _rec_started
        t1 = time.perf_counter()
        if not wav.startswith(b"RIFF") or len(wav) <= 44:
            print(f"Nemo sent no recording ({len(wav)} bytes); hold SPACE a little longer", flush=True)
            return
        settings.CAPTURES_DIR.mkdir(parents=True, exist_ok=True)
        QUESTION_WAV.write_bytes(wav)

        a = requests.post(ASK_URL, data=wav, timeout=60,
                          headers={"Content-Type": "audio/wav", "X-Device-Id": "nemo-a"})
        t2 = time.perf_counter()
        if a.status_code != 200:
            print(f"/ask failed: HTTP {a.status_code} {a.text[:200]}", flush=True)
            return
        ANSWER_WAV.write_bytes(a.content)
        question = unquote(a.headers.get("X-Question-Text", ""))
        answer = unquote(a.headers.get("X-Answer-Text", ""))
        print(f"Q: {question or '(nothing heard)'}", flush=True)
        print(f"A: {answer}", flush=True)

        p = requests.post(f"{settings.NEMO_URL}/play", timeout=60,
                          files={"file": ("answer.wav", a.content, "audio/wav")})
        p.raise_for_status()
        t3 = time.perf_counter()
        print(f"   held SPACE {held_s:.1f} s | fetch recording {(t1 - t0) * 1000:.0f} ms ({len(wav)} bytes) | "
              f"/ask {(t2 - t1) * 1000:.0f} ms | play on Nemo {(t3 - t2) * 1000:.0f} ms | "
              f"release to end {(t3 - t0):.1f} s", flush=True)
    except Exception as exc:
        print(f"error: {exc}", flush=True)
    finally:
        _busy.release()


def on_press(key):
    if key == keyboard.Key.esc:
        return False
    if key == keyboard.Key.space and not _recording and not _busy.locked():
        _start()


def on_release(key):
    global _recording
    if key == keyboard.Key.space and _recording:
        _recording = False
        # Off the keyboard thread, so the listener stays responsive while we wait.
        threading.Thread(target=_round_trip, daemon=True).start()


def _claim_single_instance() -> socket.socket:
    lock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        lock.bind(("127.0.0.1", SINGLE_INSTANCE_PORT))
    except OSError:
        raise SystemExit("talk_bridge is already running in another window. Close that one (ESC) "
                         "first, or every answer is spoken twice.")
    return lock


def main() -> None:
    if not settings.NEMO_URL:
        raise SystemExit("NEMO_URL is not set in .env (e.g. NEMO_URL=http://172.20.10.9)")
    _lock = _claim_single_instance()  # held for as long as main() runs
    print(f"Nemo: {settings.NEMO_URL} | backend: {ASK_URL}")
    print("Hold SPACE to ask, release to send. ESC quits.", flush=True)
    with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
        listener.join()


if __name__ == "__main__":
    main()

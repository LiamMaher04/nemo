"""Test POST /ask end to end: a spoken question in, a spoken answer out.

Makes "where's my remote?" as a WAV with the local Piper voice (so no mic needed), seeds the remote
on the couch, POSTs the WAV to /ask, then checks, saves and plays the reply.

Run from the repo root (TTS_PROVIDER from .env, or override it for one run):
    backend\\.venv\\Scripts\\python.exe -m backend.test_ask
    $env:TTS_PROVIDER='elevenlabs'; backend\\.venv\\Scripts\\python.exe -m backend.test_ask
WARNING: calls reset_memory first (via the agent test's seeding). Items and areas are kept.
"""

import io
import time
import wave
from urllib.parse import unquote

from fastapi.testclient import TestClient

from backend import settings, speech
from backend.main import app
from backend.test_agent import seed_placements

QUESTION = "Where's my remote?"


def describe_wav(data: bytes) -> str:
    with wave.open(io.BytesIO(data)) as w:
        secs = w.getnframes() / w.getframerate()
        return f"{w.getframerate()} Hz, {w.getnchannels()} channel(s), {w.getsampwidth() * 8}-bit, {secs:.1f} s"


def play(path) -> None:
    try:
        import winsound
        winsound.PlaySound(str(path), winsound.SND_FILENAME)
    except Exception as exc:  # not on Windows, or no audio device
        print(f"  (couldn't play it here: {exc})")


def main() -> None:
    settings.CAPTURES_DIR.mkdir(parents=True, exist_ok=True)

    print("Seeding placements:")
    seed_placements()

    question_wav = speech.tts_local(QUESTION)
    q_path = settings.CAPTURES_DIR / "ask_question.wav"
    q_path.write_bytes(question_wav)
    print(f"\nQuestion WAV ({describe_wav(question_wav)}): {q_path}")

    with TestClient(app) as client:  # runs startup, so the models load here
        started = time.perf_counter()
        r = client.post("/ask", content=question_wav,
                        headers={"Content-Type": "audio/wav", "X-Device-Id": "nemo-test"})
        secs = time.perf_counter() - started

    print(f"\nPOST /ask -> HTTP {r.status_code} in {secs:.1f} s (TTS_PROVIDER={settings.TTS_PROVIDER})")
    if r.status_code != 200:
        print("  ", r.text)
        return
    print(f"  X-Question-Text: {unquote(r.headers['X-Question-Text'])}")
    print(f"  X-Answer-Text:   {unquote(r.headers['X-Answer-Text'])}")
    print(f"  X-Voice:         {r.headers.get('X-Voice')}")
    print(f"  reply WAV: {describe_wav(r.content)}")

    a_path = settings.CAPTURES_DIR / f"ask_answer_{settings.TTS_PROVIDER}.wav"
    a_path.write_bytes(r.content)
    print(f"  saved: {a_path}")
    print("  playing...")
    play(a_path)


if __name__ == "__main__":
    main()

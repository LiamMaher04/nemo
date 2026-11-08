"""Speech for /ask: speech to text (faster-whisper) and text to speech (Piper or ElevenLabs).

Everything goes in and out as WAV: 16 kHz, mono, 16-bit PCM, which is what Nemo records and plays.
Call load() once at startup; it loads the whisper model and, for TTS_PROVIDER=local, the Piper voice.
"""

import io
import logging
import wave
from math import gcd

import httpx
import numpy as np
from scipy.signal import resample_poly

from backend import settings

log = logging.getLogger("nemo.speech")

SAMPLE_RATE = 16000
ELEVENLABS_MODEL = "eleven_flash_v2_5"  # ElevenLabs' fast, low-latency model

_whisper = None
_piper = None


# ---- WAV helpers ----

def _resample(samples: np.ndarray, rate_in: int, rate_out: int) -> np.ndarray:
    if rate_in == rate_out:
        return samples
    g = gcd(rate_in, rate_out)
    return resample_poly(samples, rate_out // g, rate_in // g)


def wav_to_float(data: bytes) -> np.ndarray:
    """Any PCM WAV -> mono float32 at 16 kHz, -1 to 1, for whisper."""
    with wave.open(io.BytesIO(data)) as w:
        channels, width, rate = w.getnchannels(), w.getsampwidth(), w.getframerate()
        raw = w.readframes(w.getnframes())
    if width != 2:
        raise ValueError(f"expected 16-bit PCM WAV, got {width * 8}-bit")
    samples = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    if channels > 1:
        samples = samples.reshape(-1, channels).mean(axis=1)
    return _resample(samples, rate, SAMPLE_RATE).astype(np.float32)


def pcm16_to_wav(pcm: np.ndarray | bytes, rate: int) -> bytes:
    """16-bit mono PCM at any rate -> WAV bytes at 16 kHz, mono, 16-bit."""
    samples = np.frombuffer(pcm, dtype="<i2") if isinstance(pcm, (bytes, bytearray)) else pcm
    samples = samples.astype(np.float32)
    samples = _resample(samples, rate, SAMPLE_RATE)
    out = np.clip(np.round(samples), -32768, 32767).astype("<i2")
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(out.tobytes())
    return buf.getvalue()


# ---- Loading ----

def load_whisper():
    global _whisper
    if _whisper is None:
        from faster_whisper import WhisperModel
        _whisper = WhisperModel(settings.STT_MODEL, device="cpu", compute_type="int8")
        log.info("loaded faster-whisper %s on CPU", settings.STT_MODEL)
    return _whisper


def load_piper():
    global _piper
    if _piper is None:
        from piper import PiperVoice
        model = settings.VOICES_DIR / f"{settings.PIPER_VOICE}.onnx"
        if not model.exists():
            raise FileNotFoundError(
                f"Piper voice not found at {model}. Download it with: "
                f"python -m piper.download_voices {settings.PIPER_VOICE} --download-dir data/voices"
            )
        _piper = PiperVoice.load(model)
        log.info("loaded Piper voice %s", settings.PIPER_VOICE)
    return _piper


def load() -> None:
    """Load the models /ask needs, once, at startup."""
    load_whisper()
    load_piper()  # always: it's the voice, or the fallback if ElevenLabs fails
    if settings.TTS_PROVIDER == "local":
        pass
    elif settings.TTS_PROVIDER == "elevenlabs":
        if not settings.ELEVENLABS_API_KEY or not settings.ELEVENLABS_VOICE_ID:
            raise RuntimeError("TTS_PROVIDER=elevenlabs needs ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID")
    else:
        raise RuntimeError(f"Unknown TTS_PROVIDER {settings.TTS_PROVIDER!r}: use local or elevenlabs")


# ---- Speech to text ----

NORMALISE_PEAK = 0.9  # scale quiet recordings so their loudest sample is about this
NORMALISE_MAX_GAIN = 30.0  # never boost more than this
NORMALISE_SILENCE = 0.001  # below this peak it's silence: leave it, don't boost noise


def normalise(samples: np.ndarray) -> np.ndarray:
    """Peak-normalise for speech to text only. Nemo's mic is quiet (about 8x too quiet to hear)."""
    peak = float(np.max(np.abs(samples))) if samples.size else 0.0
    if peak < NORMALISE_SILENCE:
        log.info("normalise: peak %.4f, too quiet to be speech, no gain applied", peak)
        return samples
    gain = min(NORMALISE_PEAK / peak, NORMALISE_MAX_GAIN)
    log.info("normalise: peak %.4f, gain %.1fx", peak, gain)
    return (samples * gain).astype(np.float32)


def transcribe(wav: bytes) -> str:
    samples = normalise(wav_to_float(wav))
    segments, _ = load_whisper().transcribe(samples, language="en", beam_size=1, vad_filter=True)
    return " ".join(s.text.strip() for s in segments).strip()


# ---- Text to speech ----

def tts_local(text: str) -> bytes:
    voice = load_piper()
    pcm = b"".join(chunk.audio_int16_bytes for chunk in voice.synthesize(text))
    return pcm16_to_wav(pcm, voice.config.sample_rate)


def tts_elevenlabs(text: str) -> bytes:
    r = httpx.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{settings.ELEVENLABS_VOICE_ID}",
        params={"output_format": "pcm_16000"},  # raw 16-bit mono PCM at 16 kHz
        headers={"xi-api-key": settings.ELEVENLABS_API_KEY},
        json={"text": text, "model_id": ELEVENLABS_MODEL},
        timeout=30.0,
    )
    if r.status_code != 200:
        raise RuntimeError(f"ElevenLabs failed ({r.status_code}): {r.text[:300]}")
    return pcm16_to_wav(r.content, SAMPLE_RATE)


def speak(text: str) -> tuple[bytes, str]:
    """Text -> (WAV at 16 kHz mono 16-bit, voice used). ElevenLabs falls back to Piper on any error."""
    if settings.TTS_PROVIDER == "elevenlabs":
        try:
            return tts_elevenlabs(text), "elevenlabs"
        except Exception as exc:
            log.warning("ElevenLabs failed, using the local voice instead: %s", exc)
    return tts_local(text), "local"

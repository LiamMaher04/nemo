"""Settings read from the .env file at the repo root."""

import os
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(REPO_ROOT / ".env")


def _clean(value: str | None, default: str) -> str:
    """Strip inline '# comments' and whitespace that .env lines may carry."""
    if value is None:
        return default
    value = value.split("#", 1)[0].strip()
    return value or default


BACKEND_HOST: str = _clean(os.getenv("BACKEND_HOST"), "0.0.0.0")
BACKEND_PORT: int = int(_clean(os.getenv("BACKEND_PORT"), "8000"))

SPACETIME_URL: str = _clean(os.getenv("SPACETIME_URL"), "https://maincloud.spacetimedb.com")
SPACETIME_DB: str = _clean(os.getenv("SPACETIME_DB"), "nemodb-g8356")
SPACETIME_TOKEN: str = _clean(os.getenv("SPACETIME_TOKEN"), "")  # optional; anonymous if empty

NEMOTRON_BASE_URL: str = _clean(os.getenv("NEMOTRON_BASE_URL"), "https://integrate.api.nvidia.com/v1")
NEMOTRON_API_KEY: str = _clean(os.getenv("NEMOTRON_API_KEY"), "")
NEMOTRON_AGENT_MODEL: str = _clean(os.getenv("NEMOTRON_AGENT_MODEL"), "nvidia/nemotron-3.5-lightning-30b-a3b")

NEMOTRON_VL_MODEL: str = _clean(os.getenv("NEMOTRON_VL_MODEL"), "nvidia/nemotron-3.5-super-vl-120b-a12b")

OPENROUTER_BASE_URL: str = _clean(os.getenv("OPENROUTER_BASE_URL"), "https://openrouter.ai/api/v1")
OPENROUTER_API_KEY: str = _clean(os.getenv("OPENROUTER_API_KEY"), "")
OPENROUTER_MODEL: str = _clean(os.getenv("OPENROUTER_MODEL"), "nvidia/nemotron-3.5-lightning:free")
OPENROUTER_VL_MODEL: str = _clean(os.getenv("OPENROUTER_VL_MODEL"), "nvidia/nemotron-3.5-super-vl:free")

# Super VL (see backend/vl.py). SUPER_VL=off turns every use of it off.
SUPER_VL: bool = _clean(os.getenv("SUPER_VL"), "on").lower() not in ("off", "false", "0", "no")
VL_SECOND_OPINION: bool = _clean(os.getenv("VL_SECOND_OPINION"), "on").lower() not in ("off", "false", "0", "no")
VL_SCENE_CHECK: bool = _clean(os.getenv("VL_SCENE_CHECK"), "on").lower() not in ("off", "false", "0", "no")
VL_SCENE_EVERY_S: int = int(_clean(os.getenv("VL_SCENE_EVERY_S"), "60"))
VL_TIMEOUT_S: float = float(_clean(os.getenv("VL_TIMEOUT_S"), "12"))

NOTIFIER_PORT: int = int(_clean(os.getenv("NOTIFIER_PORT"), "8100"))
NOTIFIER_URL: str = f"http://127.0.0.1:{NOTIFIER_PORT}"
# "on" (default) texts the carer; "off" never texts anyone (for testing). Alerts are still raised.
CARER_ALERTS: bool = _clean(os.getenv("CARER_ALERTS"), "on").lower() not in ("off", "false", "0", "no")

STT_MODEL: str = _clean(os.getenv("STT_MODEL"), "small.en")  # faster-whisper model name
TTS_PROVIDER: str = _clean(os.getenv("TTS_PROVIDER"), "local").lower()  # "local" | "elevenlabs"
PIPER_VOICE: str = _clean(os.getenv("PIPER_VOICE"), "en_US-lessac-medium")
VOICES_DIR: Path = REPO_ROOT / "data" / "voices"
ELEVENLABS_API_KEY: str = _clean(os.getenv("ELEVENLABS_API_KEY"), "")
ELEVENLABS_VOICE_ID: str = _clean(os.getenv("ELEVENLABS_VOICE_ID"), "")

NEMO_URL: str = _clean(os.getenv("NEMO_URL"), "").rstrip("/")  # Nemo's base address, e.g. http://172.20.10.9

FRAME_SOURCE: str = _clean(os.getenv("FRAME_SOURCE"), "post").lower()  # "post" | "pull"
NEMO_JPG_URL: str = _clean(os.getenv("NEMO_JPG_URL"), "")  # e.g. http://172.20.10.9/jpg, for "pull"
BURST_FRAMES: int = int(_clean(os.getenv("BURST_FRAMES"), "3"))  # pull mode: frames fetched per second, sharpest kept
# Where vision runs. Blank: on this laptop (the default, and the fallback). Set, e.g.
# http://localhost:8001: each kept-or-not frame goes to backend/vision_server.py there (a Brev GPU
# box through `brev port-forward`). See docs/brev.md.
VISION_URL: str = _clean(os.getenv("VISION_URL"), "").rstrip("/")

CAPTURES_DIR: Path = REPO_ROOT / "captures"
FRAMES_DIR: Path = CAPTURES_DIR / "frames"  # the last FRAMES_KEPT kept frames, <frame_id>.jpg
FRAMES_KEPT: int = 60
LATEST_FRAME: Path = CAPTURES_DIR / "latest.jpg"

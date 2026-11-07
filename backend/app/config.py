"""All settings come from the repo-root .env. Nothing hardcoded."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")


def env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


BACKEND_HOST = env("BACKEND_HOST", "0.0.0.0")
BACKEND_PORT = int(env("BACKEND_PORT", "8000"))

NEMOTRON_BASE_URL = env("NEMOTRON_BASE_URL", "https://integrate.api.nvidia.com/v1")
NEMOTRON_API_KEY = env("NEMOTRON_API_KEY")
NEMOTRON_AGENT_MODEL = env("NEMOTRON_AGENT_MODEL", "nvidia/nemotron-3.5-lightning-30b-a3b")
NEMOTRON_VL_MODEL = env("NEMOTRON_VL_MODEL")
NEMOTRON_THINKING = env("NEMOTRON_THINKING", "false").lower() == "true"

OPENROUTER_BASE_URL = env("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_MODEL = env("OPENROUTER_MODEL")
OPENROUTER_API_KEY = env("OPENROUTER_API_KEY")

SPACETIME_URL = env("SPACETIME_URL", "https://maincloud.spacetimedb.com").rstrip("/")
SPACETIME_DB = env("SPACETIME_DB", "nemodb-g8356")
SPACETIME_TOKEN = env("SPACETIME_TOKEN")

DETECTOR = env("DETECTOR", "yoloe")
DETECT_CONF = float(env("DETECT_CONF", "0.25"))
FRAME_MIN_WIDTH = int(env("FRAME_MIN_WIDTH", "1280"))

CAPTURES_DIR = ROOT / "captures"
CAPTURES_DIR.mkdir(exist_ok=True)

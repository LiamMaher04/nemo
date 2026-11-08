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

OPENROUTER_BASE_URL: str = _clean(os.getenv("OPENROUTER_BASE_URL"), "https://openrouter.ai/api/v1")
OPENROUTER_API_KEY: str = _clean(os.getenv("OPENROUTER_API_KEY"), "")
OPENROUTER_MODEL: str = _clean(os.getenv("OPENROUTER_MODEL"), "nvidia/nemotron-3.5-lightning-30b-a3b")

CAPTURES_DIR: Path = REPO_ROOT / "captures"
LATEST_FRAME: Path = CAPTURES_DIR / "latest.jpg"

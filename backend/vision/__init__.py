"""Nemo's vision: camera input, YOLOE detection, and instant learning from our own labelled photos.

Settings come from the repo-root .env (see .env.example): DETECTOR, DETECTOR_WEIGHTS, DETECT_CONF,
BACKEND_PORT.
"""
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = BACKEND_DIR.parent
OBJECTS_FILE = Path(__file__).resolve().parent / "objects.yaml"
TEACH_DIR = BACKEND_DIR / "data" / "teach"     # gitignored: photos can be large and personal

try:
    from dotenv import load_dotenv
    load_dotenv(REPO_DIR / ".env")
except ImportError:   # python-dotenv not installed: fall back to the real environment
    pass

# backend

Python FastAPI app on the laptop (or a Brev GPU box in cloud mode).

- `POST /frame`: gating -> detector -> tracker -> matcher -> room -> `add_sighting` on Spacetime
- `POST /ask`, `POST /ask_text`: speech-to-text -> agent -> TTS
- Contracts: see `docs/interfaces.md`. Settings: `.env` at the repo root.

## Vision tools (working now)

Detection with YOLOE, plus instant learning from our own labelled photos. Details and how to call
it from the pipeline: [vision/README.md](vision/README.md).

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate     # Python 3.11+
pip install -r requirements.txt

python live.py                  # watch what it detects (laptop webcam)
python live.py --source push    # frames POSTed by the device to /frame
python teach.py                 # freeze a frame, fix the boxes, save: it learns in ~0.3 s
python check.py                 # words only vs words + learning, on held-out test photos
python tools/fake_board.py      # pretend to be the device (POST /frame, as in docs/interfaces.md)
```

The first run downloads YOLOE (~30 MB) and its text model (~240 MB) into `backend/`. On a Mac,
allow Terminal to use the camera (System Settings > Privacy & Security > Camera).

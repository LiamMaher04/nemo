# backend

Python FastAPI app on the laptop (or a Brev GPU box in cloud mode). Run everything from the REPO ROOT.

## Setup (Windows PowerShell)

```
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
copy .env.example .env      # then paste keys into .env
python -m backend.check_keys
```

## Run

```
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

- `GET /health` frames received and fps
- `POST /frame` raw JPEG from the device. Saves `captures/latest.jpg`, runs `app/vision.py`, sends sightings to Spacetime
- `POST /ask_text` `{"question": "where's my remote?"}` -> Spacetime lookup -> Nemotron answer
- `POST /coverage` recording on/off

## Test the memory without a camera

```
python -m backend.fake_sighting seed
python -m backend.fake_sighting place remote living_room sofa_arm
python -m backend.fake_sighting where remote
```
Then ask: `curl -X POST localhost:8000/ask_text -H "Content-Type: application/json" -d '{"question":"where is my remote?"}'`
(on PowerShell use `Invoke-RestMethod` or the /docs page at http://localhost:8000/docs).

## Files

- `app/config.py` settings from `.env`
- `app/spacetime.py` reducer calls + SQL over HTTP
- `app/nemotron.py` NVIDIA API with OpenRouter fallback, thinking off by default
- `app/vision.py` **Josie: the detector pipeline goes here** (returns add_sighting dicts)
- `app/main.py` endpoints

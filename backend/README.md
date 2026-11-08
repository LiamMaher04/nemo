# backend

Python FastAPI app, on the laptop. Run from the repo root:

```
backend\.venv\Scripts\python.exe -m backend.main
```

- `frames.py`: the frame loop. `FRAME_SOURCE=pull` fetches Nemo's `/jpg` (`BURST_FRAMES` back to
  back each second, keeps the sharpest); `post` takes `POST /frame`. Then `vision.process()` and
  `add_sighting` / `add_frame` in Spacetime.
- `vision/`: sharpness and duplicate gates, YOLOE, DINOv2 (Josie). See `vision/README.md`.
- `vl.py`: Nemotron 3.5 Super VL in one background worker (second opinions, spot descriptions,
  indoors check). Never on the frame loop or the question path.
- `agent.py`: the Nemotron agent and its tools.
- `speech.py`: faster-whisper in, ElevenLabs or Piper out. `POST /ask` (WAV in, WAV out) and
  `POST /ask_text` (text in, text out).
- `alerts.py`: sends carer alerts that Spacetime raised, through `notifier/`. `CARER_ALERTS=off`
  for testing.
- `talk_bridge.py`: hold SPACE on the laptop to ask through Nemo's mic and speaker, if the
  firmware button isn't flashed.
- `static/live.html`: the live page at `/live`.
- `seed_spacetime.py`: the demo items and areas. `test_*.py`: scripts that exercise each part.

Contracts: `docs/interfaces.md`. Settings: `.env` at the repo root (see `.env.example`).

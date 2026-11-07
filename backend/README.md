# backend

Python FastAPI app on the laptop (or a Brev GPU box in cloud mode).

- `POST /frame`: gating -> detector -> tracker -> matcher -> room -> `add_sighting` on Spacetime
- `POST /ask`, `POST /ask_text`: speech-to-text -> agent -> TTS
- Contracts: see `docs/interfaces.md`. Settings: `.env` at the repo root.

# Nemo

A wearable camera for older people that remembers where everyday things were last put down, and
answers "where's my remote?" out loud with a snapshot. Carers get a live floor plan and alerts.

Built at HackUTD 2026: Zero Day by Liam, Danny, Josie and Laura.

Named after Mnemosyne, the Greek goddess of memory.

## How it works

- **Nemo device** (DFRobot ESP32-S3 AI Camera + OLED + speaker) captures frames and streams them
  over Wi-Fi. Press the button to ask a question.
- **Backend** (Python, FastAPI) detects objects (YOLOE), works out which exact object it is (DINOv2)
  and which room you're in, and reports sightings.
- **Memory** (SpacetimeDB) keeps the last place each item was seen (after 2 sightings in a row in the
  same spot), and notices when the pill box goes missing from its furniture and comes back: "used".
- **Agent** (NVIDIA Nemotron) answers questions in several steps using the memory as a tool, and
  raises proactive alerts (e.g. the pill box hasn't been used by the usual time).

## Layout

- `firmware/` Arduino sketches for the device
- `backend/` FastAPI app and vision pipeline
- `spacetime/` SpacetimeDB module and the React carer app
- `agent/` Nemotron agent
- `docs/` architecture and interface contracts

## Setup

1. `cp .env.example .env` and fill in keys.
2. Put the laptop and the device on the same phone hotspot (2.4 GHz).
3. See each folder's README.

## Privacy

No video is kept, only small snapshots of tracked objects. The mic only listens while the button is
pressed. Faces are blurred in anything stored.

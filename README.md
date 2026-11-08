# Nemo

A small device you wear that remembers where you put things and tells you when you ask.

Clip Nemo onto your shirt and go about your day. Hold its button and ask "where's my remote?", and
it answers out loud: "Your TV remote is on the arm of the sofa. I saw it there about 4 minutes
ago." If something seems off, like the pill box not moving by its usual time, a family member or
carer gets a short text, as a nudge to check in.

Built at HackUTD 2026: Zero Day by Danny Dowling, Josie Burke, Laura González and Liam Maher.

Named after Mnemosyne, the Greek goddess of memory.

## How it works

- **Nemo device** (DFRobot ESP32-S3 AI Camera, OLED, mic and speaker). Its screen only shows a
  pair of eyes. It serves its camera frame over WiFi, and its button records a question.
- **Backend** (Python, FastAPI, on a laptop for now) fetches a few frames a second and keeps the
  sharpest. YOLOE finds our things and the furniture they're on, and DINOv2 tells which area of the
  home Nemo is in and which of our things a look-alike is.
- **Memory** (SpacetimeDB, TypeScript reducers) decides what a sighting means: the last place each
  thing was seen (after 2 sightings in a row in the same spot), when the pill box was used, and
  when to raise a carer alert.
- **Agent** (NVIDIA Nemotron 3.5 Lightning) answers questions in several steps, using the memory
  as tools. **Nemotron 3.5 Super VL** describes each spot, settles look-alikes, answers detail
  questions about a snapshot, and checks indoors or outdoors once a minute.
- **Speech**: faster-whisper hears the question, ElevenLabs (or Piper offline) speaks the answer.
- **Carer texts** go out by iMessage through Photon's Spectrum SDK. One way only.
- **Live page** at `http://<laptop>:8000/live` shows what Nemo sees and remembers, for demos.

What it tracks today: keys, reading glasses, the TV remote and a pill box, plus a wallet, phone and
toothbrush in the hotel demo set.

## Layout

- `firmware/` Arduino sketches for the device; the working one is
  `firmware/tests/camera_blink_audio`
- `backend/` FastAPI app: frames, vision (`backend/vision/`), agent, speech, Super VL, live page
- `spacetime/` SpacetimeDB module (tables and reducers)
- `notifier/` Bun service that sends carer texts through Photon
- `website/` marketing site
- `docs/interfaces.md` the contracts between the parts

## Setup

1. `cp .env.example .env` and fill in keys.
2. Put the laptop and the device on the same phone hotspot (2.4 GHz; iPhone: Maximise
   Compatibility).
3. Backend: `backend\.venv\Scripts\python.exe -m backend.main` from the repo root, then open
   `http://localhost:8000/live`.
4. See each folder's README.

## Privacy

No video is kept, only small snapshots of tracked things. The mic is on only while the button is
held. Faces are blurred before anything is saved. Some work happens online: snapshots go to
Nemotron and SpacetimeDB, and the words you asked go to the speech and agent services.

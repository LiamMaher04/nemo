# Nemo

**Not a chatbot. A second memory.**
A wearable memory assistant for people living with memory loss.

Nemo sits on your shirt and quietly notices where everyday things get put down. Hold its button
and ask "where are my glasses?", and it answers out loud: "On the bedside table, twelve minutes
ago." No tags, no app, no screen. If something seems off, like the pills not moving by their
usual time, the wearer gets a gentle spoken reminder first, and then a family member or carer gets
a short text as a nudge to check in.

Built at HackUTD 2026: Zero Day by Danny Dowling, Josie Burke, Laura González and Liam Maher.
Named after Mnemosyne, the Greek goddess of memory.

## How it works

- **Nemo, the device** (DFRobot ESP32-S3 AI Camera, OLED, mic and speaker, 3D-printed case, pocket
  power bank). Its screen only shows a pair of eyes. It serves camera frames over WiFi, and its
  button is push-to-talk: hold, ask, release, and it plays the spoken answer.
- **Seeing** (Python, FastAPI, on a laptop): every second the backend pulls a burst of frames and
  keeps the sharpest, drops blurry and repeated ones, and blurs faces. YOLOE finds our things and
  the furniture they're on from text descriptions. DINOv2 tells which area of the home Nemo is in
  (no markers) and which of our things a look-alike is. This step can run on a Brev GPU instead of
  the laptop (`docs/brev.md`).
- **Remembering** (SpacetimeDB, TypeScript reducers): the memory logic lives in reducers, not in
  Python. A thing only moves in memory after 2 sightings in a row in the same spot. The pill
  bottle counts as used when its spot is seen empty and it comes back, and uses are counted by
  hour, so Nemo learns the usual pill time. A scheduled reducer checks every minute whether
  anyone needs a nudge.
- **Answering** (NVIDIA Nemotron 3.5 Lightning): an agent that plans its own steps and calls tools:
  `find_item`, `where_is`, `item_history`, `look_at_snapshot` and `send_carer_alert` (only when the
  wearer asks to pass something on, or says they've fallen or need help). It answers only from what
  the tools return and says so when it hasn't seen something.
- **Looking closer** (NVIDIA Nemotron 3.5 Super VL, in the background so it never slows an answer):
  describes the exact spot when something is put down, gives a second opinion on look-alikes,
  answers the agent's snapshot questions, checks indoors or outdoors once a minute, and confirms a
  possible fall.
- **Speech**: faster-whisper hears the question on the laptop. ElevenLabs speaks the answer, with
  Piper as an offline fallback.
- **Reminders and carer texts**: a spoken pill reminder on Nemo's speaker around the usual time.
  Carer texts go out by iMessage through Photon's Spectrum SDK, one way only, for: pills not taken
  by the usual time, no activity for hours in the daytime, the wearer gone outdoors, a possible
  fall (camera only: a long dark or still floor or ceiling view, confirmed by Super VL), or a
  message the wearer asked Nemo to pass on. Every text starts "Nemo here." and is a nudge, not a
  diagnosis.
- **Live page** at `http://<laptop>:8000/live`: what Nemo sees and remembers, for demos.

What it tracks in the demo: keys, reading glasses, the TV remote and a pill bottle, plus a wallet,
phone and toothbrush in the hotel demo set.

## Layout

- `firmware/` Arduino sketches for the device; the working one is
  `firmware/tests/camera_blink_audio`
- `backend/` FastAPI app: frames, vision (`backend/vision/`), agent, speech, Super VL, live page
- `spacetime/` SpacetimeDB module (tables and reducers)
- `notifier/` Bun service that sends carer texts through Photon
- `grab.py`, `viewer.py` capture reference photos and view Nemo's camera (see Setup)
- `website/` marketing site
- `docs/interfaces.md` the contracts between the parts

## Setup on a new laptop (Windows)

1. Clone the repo and `cd` into it.
2. Python 3.11 venv and packages:
   ```
   py -3.11 -m venv backend\.venv
   backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt -r backend\vision\requirements.txt
   ```
3. `.env`: copy `.env.example` to `.env`, then get the real keys from Liam (they're never in git).
   Set `NEMO_JPG_URL` and `NEMO_URL` to the address on Nemo's screen.
4. Reference photos (not in git, too big and private): get the `captures\grab\sorted` folder from
   Liam and put it at the same path, or point `REFS_DIR` at your own capture.
5. Put the laptop and the device on the same phone hotspot (2.4 GHz; iPhone: Maximise
   Compatibility).
6. Run the backend from the repo root, then open `http://localhost:8000/live`:
   ```
   backend\.venv\Scripts\python.exe -m backend.main
   ```
   YOLOE and DINOv2 weights download themselves on the first run.
7. Optional, in their own terminals:
   - Ask through Nemo with the laptop's space bar: `backend\.venv\Scripts\python.exe -m backend.talk_bridge`
   - Carer texts: `cd notifier`, `bun install`, `bun run start`
   - Vision on a Brev GPU instead of the laptop: `docs/brev.md`

Handy tools in the repo root:
- `viewer.py`: live view of Nemo's camera. `backend\.venv\Scripts\python.exe viewer.py http://<Nemo's IP>/jpg`
- `grab.py`: capture reference photos for an area, keeping only sharp, new frames.
  `backend\.venv\Scripts\python.exe grab.py desk --url http://<Nemo's IP>/jpg` (P pause, Space save,
  Q quit; type a new area name + Enter to switch folders). Frames go to `captures/grab/<area>/`.

See each folder's README for more.

## Built with

NVIDIA Nemotron 3.5 Lightning and Super VL (build.nvidia.com), NVIDIA Brev, SpacetimeDB, Photon
Spectrum, YOLOE, DINOv2, faster-whisper, ElevenLabs, Piper, FastAPI, Bun, Arduino on the ESP32-S3.

## Privacy

No video is kept, only small snapshots of tracked things. The mic is on only while the button is
held. Faces are blurred before anything is saved. Some work happens online: snapshots go to
Nemotron and SpacetimeDB (and frames to our Brev GPU when `VISION_URL` is set), and the words you asked go to the speech and agent services.

# Nemo: context for Claude Code

HackUTD 2026 (Zero Day), UT Dallas, Sat 7 to Sun 8 Nov 2026. Team: Liam, Danny, Josie, Laura.
Times are Dallas time (CT). Submission was noon Sunday last year; check Devpost for 2026.

## What Nemo is

A wearable camera for older people living at home. It clips onto a shirt, notices where everyday
objects get put down, and when you press its button and ask "where's my remote?" it answers out loud
and shows the snapshot on its small screen. A carer (family member) gets a web app with a live floor
plan of where things are, plus alerts.

- Always call the product **Nemo**, or "the device" for the hardware. Never "the clip".
- Name comes from Mnemosyne, Greek goddess of memory.
- Demo objects: **keys, glasses, TV remote**. A **pill box** for the proactive alert.
- Demo: put the remote down, walk away, ask "where's my remote?", get "On the arm of the sofa in the
  living room, 4 minutes ago" plus the snapshot.

## Tracks (the architecture is shaped by these)

- **Spacetime (Clockwork Labs):** Spacetime must power the app's *primary functionality*. For Nemo
  that's the memory. So the memory LOGIC (stationary rule, placed vs carried, where_is) lives in
  Spacetime reducers, not in Python. If Python decides everything and Spacetime only stores rows, we
  fail their rule. Public GitHub repo required to win.
- **NVIDIA, "Use Nemotron beyond a chatbot":** needs multi-step workflows, tool use, beyond a chatbot,
  real-world use. So Nemotron is an *agent* with tools (Spacetime queries, VL on snapshots, TTS, carer
  alerts), and it's proactive (pill box not moved by 11am, alert the carer).

## Architecture

```
Nemo device (ESP32-S3 camera, Arduino)
  | JPEG ~1 fps over Wi-Fi (phone hotspot), POST /frame
  | button press: audio, POST /ask -> plays the WAV it gets back
  v
backend/ (Python, FastAPI, runs on the laptop; same code can run on a Brev GPU box)
  gating (blur/duplicates) -> detector (YOLOE or YOLO-World) -> tracker -> instance match (DINOv2)
  -> room guess (QR/AprilTag markers first, walkthrough matching later)
  | HTTP: POST /v1/database/<db>/call/add_sighting
  v
spacetime/ (SpacetimeDB module in TypeScript + React carer app)
  tables + reducers: add_sighting, stationary rule, item_state, where_is
  |                         |
  v                         v
agent/ (Nemotron)        carer app (subscribes live): floor plan, pins, snapshots, Ask box
```

- **Local first.** Demo runs on the laptop on the same phone hotspot as the device. Every URL is a
  setting in `.env` (device firmware: a #define), never hardcoded. Cloud mode (Brev GPU + Maincloud)
  is the same code with different URLs.
- The ESP32 is 2.4 GHz only and can't join eduroam or captive-portal Wi-Fi. Use a phone hotspot.

## Repo layout and owners (owners still to confirm in the team Google Doc)

- `firmware/` Arduino sketches for the DFR1154 (Danny, Laura)
- `backend/` FastAPI app: /frame, /ask, vision pipeline, speech (vision: Josie)
- `spacetime/` SpacetimeDB module + React carer app (Liam)
- `agent/` Nemotron agent and its tools (Liam)
- `docs/` architecture and the interface contracts. **Read `docs/interfaces.md` before changing any
  endpoint, reducer or table.** If you change a contract, update that file in the same commit.

## Build order (do not skip ahead)

1. Device POSTs one JPEG per second to the laptop. (critical path)
2. Python calls `add_sighting` on Spacetime and a pin shows up live in the React app.
3. Detector finds keys/glasses/remote in real frames and feeds step 2.
4. `/ask`: speech-to-text -> `where_is` -> one Nemotron call to phrase it -> TTS -> WAV back to device.
5. Only then: multi-step agent, proactive alerts, DINOv2 look-alikes, room walkthrough, Brev, Maincloud.

A crude end-to-end loop beats any polished part. Get the loop working first.

## Key decisions and gotchas

- **Nemotron:** build.nvidia.com API (OpenAI-compatible) by default, OpenRouter as fallback. Switch via
  `NEMOTRON_BASE_URL` / `NEMOTRON_MODEL`. Reasoning is off by default; `/think` in the system prompt
  turns it on (use only for the harder multi-step questions, it slows the answer).
- **Spacetime from Python:** no Python SDK. Call reducers over HTTP:
  `POST {SPACETIME_URL}/v1/database/{SPACETIME_DB}/call/{reducer}` with a JSON array of the reducer's
  arguments as the body. Check the current docs (spacetimedb.com/docs) for auth headers.
- **Detector prompts:** "eyeglasses" not "glasses", "tv remote control", "house keys on keyring",
  "pill organizer box". Also detect "hand" (carried vs put down) and furniture (table, sofa, counter).
- **Camera:** OV3660, 160 degree fisheye, no IR-cut filter (colours wash out, don't rely on colour),
  chest-mounted ~15 degrees down. Keep frames at 1280 px+ or keys vanish. Edge-of-frame detections are
  low confidence.
- **Firmware:** board "ESP32S3 Dev Module", PSRAM "OPI PSRAM" or the camera won't start.
  `WiFi.setSleep(false)` so the power bank doesn't switch off. OLED on `Wire.begin(43, 44)`.
  Don't hold BOOT while plugging in. Start at 1 fps; the board runs hot.
- **Put down vs carried:** hand overlap is only a hint. The real commit signal is "same item, same
  place, N frames in a row, no hand". That decision happens in the Spacetime reducer.
- **Privacy:** no video kept, only small snapshot thumbnails of tracked objects. Mic only on button
  press. Blur faces before storing anything. Out of scope: face/person recognition, video replay,
  outdoor/GPS, medical claims.
- **Secrets:** API keys live in `.env` only (gitignored). This repo is public. Never commit a key,
  never print one in logs.
- MLH rule: project code is written at the event. Fine to use libraries, vendor examples and models.

## Style

- Python 3.11+, FastAPI, type hints, small modules. TypeScript for Spacetime and the app.
- Prefer simple and working over clever. Log timings (frame-to-sighting, question-to-answer).
- Comments and docs in plain English, Irish/British spelling, no em dashes.

## Links

- Team Google Doc (source of truth for decisions and to-dos):
  https://docs.google.com/document/d/1q5qitB92fZYmmpDA1Q_zDDj2VxVUKpsluMAjhFDaU1I/edit
- Architecture doc for the vision side: https://claude.ai/artifact/LoAKG6JUq5MGNHYrKAkE29

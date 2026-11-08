# Nemo: context for Claude Code

HackUTD 2026 (Zero Day), UT Dallas, Sat 7 to Sun 8 Nov 2026. Team: Liam, Danny, Josie, Laura.
Times are Dallas time (CT). Submission was noon Sunday last year; check Devpost for 2026.

## What Nemo is

A wearable camera for older people living at home. It clips onto a shirt and notices where everyday
objects get put down. One button: hold it, ask out loud ("where's my remote?"), and the answer is
spoken on Nemo's speaker. The OLED only shows eyes: awake when Nemo is on, closed when it's off.
Nothing else goes on the screen.

**How to work in this repo:** Liam decides what gets built, step by step. Only build exactly what
the current request asks for. Don't add features, files, endpoints or scaffolding nobody asked for.
If something else seems needed, suggest it and wait.

- Always call the product **Nemo**, or "the device" for the hardware. Never "the clip".
- Name comes from Mnemosyne, Greek goddess of memory.
- Demo objects: **keys, glasses, TV remote**. A **pill box** for the reminders and carer alerts.
- Demo: put the remote down, walk away, hold the button, ask "where's my remote?", hear "On the arm
  of the sofa in the living room, 4 minutes ago".

## Tracks (the architecture is shaped by these)

- **NVIDIA, "Use Nemotron beyond a chatbot":** Nemotron is an *agent* with tools, working in several
  steps, not a chatbot. It's also proactive (reminders, carer alerts).
- **Spacetime (Clockwork Labs):** Spacetime powers the primary functionality, the memory. The memory
  LOGIC (last seen, used) lives in Spacetime reducers, not in Python. If Python decides
  everything and Spacetime only stores rows, we fail their rule. Public GitHub repo required to win.
- **Photon:** carer alerts go out by iMessage/SMS through Photon's Spectrum TypeScript SDK. One way
  only: Nemo texts the carer, the carer doesn't text back.

## Models

- **YOLOE (`yoloe-26s-seg`):** finds items and furniture in every kept frame. Furniture is only ever
  a place, never an item.
- **DINOv2:** matches each frame to pre-recorded clips of each area to say where the wearer is (no
  QR markers), and tells look-alike items apart.
- **Nemotron 3.5 Super VL:** describes the spot when an item is put down, checks indoors vs outdoors
  once a minute, and is a tool the agent uses to double-check a location or confirm a fall.
- **Nemotron 3.5 Lightning:** the agent.

Agent tools: `find_item`, `where_is`, `item_history`, `look_at_snapshot` (Super VL),
`send_carer_alert` (Photon). Details in `docs/interfaces.md`.

## Architecture

```
Nemo device (ESP32-S3 camera, Arduino)
  | captures ~5-10 frames/s, sends the sharpest each second (1024 px+), POST /frame
  | hold button: records 16 kHz mono WAV, POST /ask, plays the WAV it gets back
  |   (until the firmware button lands, backend/talk_bridge.py does this from the laptop)
  | reminders: the backend POSTs a WAV to Nemo's /play
  v
backend/ (Python, FastAPI, on the laptop)
  drop blurry and near-duplicate frames -> YOLOE (items + furniture) -> DINOv2 (area, look-alikes)
  | HTTP: add_sighting per item seen, then add_frame once per kept frame
  v
spacetime/ (SpacetimeDB module in TypeScript)
  tables + reducers: last seen, used, item_state, routines, alerts
  |
  v
agent (Nemotron Lightning + tools) -> spoken answers and reminders on Nemo
                                   -> carer texts via Photon
```

- **Local first.** The demo runs on the laptop on the same phone hotspot as the device. Every URL is
  a setting in `.env` (device firmware: a #define in `secrets.h`), never hardcoded.
- The ESP32 is 2.4 GHz only and can't join eduroam or captive-portal Wi-Fi. Use a phone hotspot
  (iPhone: turn on Maximise Compatibility).

## How the memory decides (reducer rules)

Spacetime keeps the last place each item was seen. Seeing an item in someone's hand now and then
is fine: the last place Nemo saw it is still a useful answer.

- **Last seen:** once an item has been seen `CONFIRM_FRAMES` (2) times in a row in the same area and
  furniture, `item_state` is updated to that spot. It's a noise filter: one stray sighting changes
  nothing. A `placed` event is written only when the area or furniture actually changes.
- **add_frame:** vision reports each kept frame (area, furniture in view, items seen, sharpness).
  If an important item's furniture is clearly in view (sharp frame) and the item isn't there, it's
  marked missing. `item_state` doesn't change: looking the other way, or a blurry frame, changes
  nothing.
- **Used:** an important item (the pill box) that was missing from its furniture in a sharp frame
  is seen back on the same furniture in the same area. That writes a `used` event and adds to
  `routines` for that hour. A sign the pills were taken, not proof.
- **Small DINOv2 margin** (two look-alikes are close): store both candidates, change neither item.

## Alerts

- **Spoken reminders to the wearer** on Nemo's speaker, e.g. around their usual pill time.
- **Carer texts via Photon:**
  - left the house (Super VL says outdoors);
  - pills not taken by the usual time;
  - possible fall: a jolt, then black or a fixed floor/ceiling view for 30 to 60 s, confirmed by
    Super VL;
  - no activity for hours during the daytime.

## Repo layout and owners

- `firmware/` Arduino sketches for the device (Laura, Danny). Hardware tests in `firmware/tests/`.
- `backend/vision/` frame in, sightings out (Josie).
- `backend/` the rest of the API: /frame, /ask, speech (Liam).
- `spacetime/` SpacetimeDB module (Liam).
- `agent/` Nemotron agent, its tools and the alerts (Liam).
- `website/` marketing site (Laura).
- `docs/` the interface contracts. **Read `docs/interfaces.md` before changing any endpoint, reducer
  or table.** If you change a contract, update that file in the same commit.

## Build order (do not skip ahead)

1. Frames to `/frame` (firmware + endpoint).
2. Spacetime tables and the last-seen reducer, plus seed data for the demo items and areas.
3. Vision v1 (Josie).
4. Teach YOLOE on footage from the hotel and the demo room.
5. `/ask` voice + agent.
6. Super VL spot description.
7. Photon alerts + the outdoor check.
8. Routines, "used", spoken reminders.
9. Video and rehearsal.

A crude end-to-end loop beats any polished part. Get the loop working first.

## Out of scope

QR markers, the carer app, texting back, face recognition, medical claims, no-record zones.

## Key decisions and gotchas

- **Nemotron:** build.nvidia.com API (OpenAI-compatible, base `https://integrate.api.nvidia.com/v1`),
  OpenRouter as fallback. Agent = `NEMOTRON_AGENT_MODEL` (Nemotron 3.5 Lightning). Vision =
  `NEMOTRON_VL_MODEL` (Nemotron 3.5 Super VL). Thinking is toggled per call with
  `extra_body={"chat_template_kwargs":{"enable_thinking": bool}}` (plus `reasoning_budget`); keep it
  off for quick spoken answers. Streamed thinking arrives in `delta.reasoning_content`, never speak
  that, only `delta.content`.
- **Speech:** speech to text with faster-whisper (also test Nemotron 3 Nano Omni). Text to speech
  produces the WAV the device plays.
- **Spacetime:** database `nemodb-g8356` on Maincloud (`spacetime dev nemodb-g8356 --server maincloud`).
  Local `spacetime start` is the fallback if the venue internet dies.
- **Spacetime from Python:** no Python SDK. Call reducers over HTTP:
  `POST {SPACETIME_URL}/v1/database/{SPACETIME_DB}/call/{reducer}` with a JSON array of the reducer's
  arguments as the body. Check the current docs (spacetimedb.com/docs) for auth headers.
- **Camera:** OV3660, 160 degree fisheye, no IR-cut filter (colours wash out, don't rely on colour),
  chest-mounted about 15 degrees down. Keep frames at 1024 px or more (XGA) or keys vanish.
  Edge-of-frame detections are low confidence.
- **Firmware:** board "ESP32S3 Dev Module", PSRAM "OPI PSRAM" or the camera won't start.
  `WiFi.setSleep(false)` so the power bank doesn't switch off. OLED on `Wire.begin(43, 44)`.
  Don't hold BOOT while plugging in. The board runs hot.
- **Privacy:** no video kept, only small snapshot thumbnails of tracked objects. Mic only while the
  button is held. Blur faces before storing anything.
- **Secrets:** API keys live in `.env` only (gitignored), Wi-Fi details in `firmware/secrets.h`
  (gitignored). This repo is public. Never commit a key, never print one in logs.
- MLH rule: project code is written at the event. Fine to use libraries, vendor examples and models.

### Demo sets

Two demo setups. The hotel set (room "hotel room": sofa, desk, fridge, TV, bedside table, bathroom)
is for the demo video. The venue set (room "venue") is the judging table; its areas get added once we
see it. Both are seeded together, and Nemo only reports areas it has seen. Vision will pick which
set's area references to load with a `DEMO_SET` setting, added when the DINOv2 branch is merged.

## Style

- Python 3.11+, FastAPI, type hints, small modules. TypeScript for Spacetime and Photon.
- Prefer simple and working over clever. Log timings (frame-to-sighting, question-to-answer).
- Comments and docs in plain English, Irish/British spelling, no em dashes.

## Links

- Team Google Doc (source of truth for decisions and to-dos):
  https://docs.google.com/document/d/1q5qitB92fZYmmpDA1Q_zDDj2VxVUKpsluMAjhFDaU1I/edit
- Architecture doc for the vision side: https://claude.ai/artifact/LoAKG6JUq5MGNHYrKAkE29

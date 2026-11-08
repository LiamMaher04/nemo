# Interfaces (the contracts between the parts)

Agree these first so everyone can build in parallel. Change a contract only in this file, in the same
commit as the code change, and tell the team.

## 1. Device -> backend (HTTP, plain, same hotspot)

### POST /frame
- Body: raw JPEG bytes. `Content-Type: image/jpeg`.
- Headers: `X-Device-Id: nemo-a`, `X-Frame-Ts: <ms since device boot>` (optional).
- Response: `200 {"ok": true}`. The device ignores the body; it just keeps sending.
- In post mode the device sends one frame a second (the plan was the sharpest of 5 to 10). The
  demo runs pull mode instead (below), where the backend picks the sharpest.
- Resolution 1024 px wide or more (XGA, 1024x768; keys are tiny).
- The backend also drops blurry and near-duplicate frames before running any models.
- The reply comes straight away (`{"ok": true}`, or `{"ok": true, "skipped": "busy"}`); vision
  runs in the background.

### Frame source (`FRAME_SOURCE` in `.env`)
- `post` (default): Nemo POSTs each JPEG to `/frame`, as above.
- `pull` (what the demo runs): every second the backend fetches Nemo's `GET /jpg` at
  `NEMO_JPG_URL` (e.g. `http://172.20.10.9/jpg`) `BURST_FRAMES` (3) times back to back, scores each
  with the vision sharpness function (about 20 ms each) and processes only the sharpest. A `503`
  (Nemo is recording) or no answer skips that second.

Both go through the same handler (`backend/frames.py`):
1. `backend.vision.process(jpeg, frame_id, ts_ms)` (Josie's code). `frame_id` keeps counting up
   across restarts (it carries on from the newest saved frame); `ts_ms` is UTC ms.
2. For a kept frame: `add_sighting` once per sighting, then `add_frame` once, over HTTP.
3. The kept frame is saved as `captures/frames/<frame_id>.jpg`; only the last 60 are kept, for
   Super VL (spot descriptions, second opinions, `look_at_snapshot`).
4. Super VL is handed the kept frame in the background (section 3, "Super VL"). The frame loop
   never waits for it.
- Only one frame is processed at a time. A frame that arrives while another is still being
  processed (or while YOLOE is loading at startup) is skipped, not queued.
- Each frame logs vision time, Spacetime time and total. `GET /health` adds `frame_source` and
  `vision` (processed, kept, dropped, skipped_busy, spacetime_errors, avg_vision_ms_last_20).
- `area_id` is `""` (and `area_conf` low) when DINOv2 can't tell the area from its reference
  photos (`REFS_DIR`); see `backend/vision/README.md`.

### Where vision runs (`VISION_URL` in `.env`)
- Blank (the default, and the fallback): `backend.vision.process()` runs on the laptop, as above.
- Set (e.g. `http://localhost:8001`): `frames.py` doesn't load YOLOE or DINOv2. It POSTs each frame
  to `{VISION_URL}/process` (`backend/vision_server.py`, normally on a Brev GPU box through
  `brev port-forward`; setup in `docs/brev.md`) and rebuilds the same `VisionResult` from the
  reply, so Spacetime, the saved frames, `/live` and Super VL work unchanged. `result.ms` is the
  round trip; each frame logs `vision N ms (server N ms, network N ms)`.
- Timeout 3 s. A frame that errors or times out is skipped (`stats.remote_errors`), with one
  warning line at most every 30 s. No switching back mid-run: blank `VISION_URL` and restart.
- At startup the backend calls the server's `/health` once and logs what it found.
- On Windows prefer `127.0.0.1` to `localhost` in `VISION_URL`: `localhost` tries IPv6 first and
  costs about 2 s each time a connection is reopened.
- `GET /health` on the backend shows `vision.mode` (`local` | `remote`) and `vision.url`.

### Vision server (`backend/vision_server.py`)
Runs Josie's pipeline on its own, with the vision settings from its own repo-root `.env` (they
must match the laptop's). No API keys. Loads YOLOE, DINOv2 and the reference fingerprints once at
startup, on CUDA if there is one. One frame at a time (the gate and area vote keep state).
`uvicorn backend.vision_server:app --host 127.0.0.1 --port 8001`

`POST /process`
- Body: raw JPEG. Headers: `X-Frame-Id` (int), `X-Frame-Ts` (UTC ms, float). Both required.
- Response `200`: every `VisionResult` field as JSON: `kept`, `drop_reason`, `sharpness`,
  `sightings` (14 keys each, `add_sighting` order, with `thumb_b64`), `frame` (`add_frame` order,
  or `null`), `furniture_boxes` (`[name, wording, [x, y, w, h], conf]`), `matched_by`, `ms`
  (time in `process()`), `yoloe_ms`, `dino_ms`, `area` (the `AreaMatch` fields, or `null`), plus
  `server_ms` (the whole request as the server saw it). `400` for a non-JPEG body or missing
  headers, `503` if the models didn't load.

`GET /health`
- `ok`, `loaded`, `error`, `load_s`, `device` (YOLOE: `cuda` | `mps` | `cpu`), `dino_device`,
  `cuda`, `gpu` (name or `null`), `refs_dir`, `area_refs` and `item_refs` (photos per folder), and
  `settings` (`SHARPNESS_GATE`, `DETECT_CONF`, `DETECT_IMGSZ`, `DETECTOR_WEIGHTS`, `DINO_MODEL`) to
  check against the laptop's.

### POST /ask
- The wearer holds the button and asks out loud. The device records while the button is held.
- Body: raw audio. `audio/wav`, 16 kHz, mono, 16-bit PCM. (Other rates or stereo are converted.)
- Headers: `X-Device-Id`.
- Backend (`backend/speech.py`, models loaded once at startup):
  - speech to text: faster-whisper, `STT_MODEL` (default `small.en`; the demo `.env` uses
    `base.en`, which is faster), on CPU, int8. The audio is
    peak-normalised first (loudest sample to about 0.9, at most 30x gain, nothing if the peak is
    under 0.001), because Nemo's mic is quiet. Only for speech to text, never for what's played;
  - the same agent as `/ask_text`;
  - text to speech, by `TTS_PROVIDER`: `local` = Piper (`PIPER_VOICE`, files in `data/voices/`,
    offline, no key), `elevenlabs` = `ELEVENLABS_API_KEY` + `ELEVENLABS_VOICE_ID`, model
    `eleven_flash_v2_5`, `pcm_16000` output. If ElevenLabs fails for any reason, the answer is
    spoken with the local Piper voice instead (Piper is always loaded). ElevenLabs' free plan
    can't use voice-library voices over the API (402); use a default voice or a paid plan.
  - Also test Nemotron 3 Nano Omni for speech to text later.
- Response: `200`, `Content-Type: audio/wav`, 16 kHz, mono, 16-bit PCM (the spoken answer, played
  on Nemo's speaker), with headers `X-Question-Text` and `X-Answer-Text` (UTF-8, percent-encoded)
  and `X-Voice` (`local` | `elevenlabs`, the voice actually used).
  If nothing was heard it still answers out loud ("Sorry, I didn't catch that..."). `400` if the
  body isn't a WAV, `503` if speech didn't load at startup.
- Each part is timed in the log: speech to text, agent, text to speech, total.

### POST /ask_text
- Text in, text out, for testing the agent without the device (no speech).
- Body: `{"question": "where's my remote?"}`
- Response: `200 {"answer": "...", "tool_calls": [{"name", "args", "result", "ms"}, ...]}`.
  `503` if no model provider could answer.

### Nemo's own endpoints (device side, served by the board)
Nemo runs a small web server on its own IP (`NEMO_URL`, e.g. `http://172.20.10.9`, shown on the
OLED). Firmware: `firmware/tests/camera_blink_audio` (Laura).

| endpoint | what it does |
|---|---|
| `GET /jpg` | the current camera frame as a JPEG. `503` while Nemo is recording: the backend's pull loop skips that second quietly. |
| `GET /rec/start` | start recording the mic (up to 15 s). |
| `GET /rec/stop` | stop, and return the recording as a WAV: 16 kHz, mono, 16-bit. |
| `POST /play` | multipart form, field `file` = a WAV (16 kHz mono 16-bit, up to 15 s): Nemo speaks it. Answers once playback has finished. |
| `GET /play_last` | play the last recording back (mic + speaker echo test, with 8x gain). |

**Asking (the button):** in `camera_blink_audio` the BOOT button records while held, then POSTs
the WAV straight to `BACKEND_ASK_URL` (the backend's `/ask`, timeout 30 s, with
`X-Device-Id: nemo-a`) and plays the reply. If `/ask` can't be reached it plays the recording
back instead. `BACKEND_ASK_URL` is a constant in the sketch, so it has to match the laptop's IP on
the hotspot. `backend/talk_bridge.py` does the same from the laptop (hold SPACE -> `/rec/start`,
release -> `/rec/stop` -> `POST /ask` -> `POST {NEMO_URL}/play`), for when the button sketch isn't
flashed. Only run one copy (it holds a lock on port 47613).

**Spoken alerts:** the backend's sender loop POSTs a WAV to Nemo's `/play` (multipart `file`) for
every unsent alert with channel `"spoken"` (section 5), e.g. the pill reminder.

**Fall check:** every frame Nemo returns, kept or dropped, also goes through `backend/fall.py`
before vision (section 5, "Possible fall").

The OLED only ever shows eyes (awake when on, closed when off). Nothing from the backend goes on it.

### GET /live (the "what Nemo sees" page)
A browser page served by the backend for demos and debugging: `http://<laptop>:8000/live`. It shows
the latest processed frame with YOLOE's boxes drawn on it (solid coral = one of our things, dashed
coral = not sure which, with its look-alike candidates, dashed aqua = furniture; every box is
labelled in words too), DINOv2's area vote and confidence, the sharpness score against the gate,
kept/dropped verdicts, per-frame timings, a feed of recent frames, what Spacetime currently
remembers (with thumbnails and Super VL's spot sentence), the last spoken question and answer, and
how each step works. Everything on it comes from the real pipeline output; nothing is drawn that a
model didn't return. It follows the brand guidelines (cream, navy, Poppins and Inter, 16px labels
and 18px text minimum, works at phone width). Fonts come from Google Fonts, with the system font
as fallback if the laptop is offline.
- `GET /live/state`: JSON the page polls every 0.5 s: `frame` (frame_id, kept, drop_reason,
  sharpness, sharpness_gate, area_id, area_conf, items_seen, sightings without thumbnails,
  furniture boxes, vision_ms, spacetime_ms), `stats`, `feed` (last 40 frames), `memory`
  (item_state rows with spot phrases and thumb_b64, cached 2 s), `last_ask`, `config`, `vl`
  (Super VL: on, model, calls, failed, dropped, avg_ms, last answer).
- `GET /live/frame.jpg`: the latest processed JPEG (kept or dropped), `204` before the first frame.
The page reads from the backend only, never from Nemo, so it doesn't compete for Nemo's camera.

## 2. Backend -> Spacetime (reducer calls over HTTP)

`POST {SPACETIME_URL}/v1/database/{SPACETIME_DB}/call/{reducer}`
Body is a JSON array of the reducer's arguments, in order.

### add_sighting
One identified (or ambiguous) item in one kept frame. Python reports what it SAW. Spacetime decides
what it MEANS (last seen, used).

Arguments, in this order:

| # | arg | type | notes |
|---|---|---|---|
| 1 | ts_ms | f64 | UTC ms since epoch |
| 2 | frame_id | f64 | backend's frame counter |
| 3 | area_id | string | DINOv2 match against the pre-recorded area clips |
| 4 | area_conf | f32 | 0 to 1 |
| 5 | label | string | YOLOE class |
| 6 | det_conf | f32 | 0 to 1 |
| 7 | item_id | string | best match, `""` if ambiguous |
| 8 | candidates_json | string | e.g. `[["reading_glasses",0.82],["sunglasses",0.79]]` |
| 9 | match_margin | f32 | DINOv2 top 1 minus top 2 similarity |
| 10 | furniture | string | furniture the item is on or near, `""` if none |
| 11 | rel_pos_json | string | `[x, y]`, 0 to 1, relative to the furniture box |
| 12 | sharpness | f32 | frame sharpness score |
| 13 | bbox_json | string | `[x, y, w, h]` in pixels of the full frame |
| 14 | thumb_b64 | string | small JPEG thumbnail, base64. Faces blurred. |

Furniture is only ever a place, never an item: it fills `furniture`, never `item_id` or `label`.

### add_frame
Called by vision once per kept frame, after that frame's `add_sighting` calls. Lets Spacetime tell
when an important item's furniture was clearly in view without the item on it.

Arguments, in this order:

| # | arg | type | notes |
|---|---|---|---|
| 1 | ts_ms | f64 | UTC ms since epoch |
| 2 | frame_id | f64 | same counter as `add_sighting` |
| 3 | area_id | string | DINOv2 area match for the frame |
| 4 | area_conf | f32 | 0 to 1 |
| 5 | furniture_in_view_json | string | furniture YOLOE found in the frame, e.g. `["desk","sofa"]` |
| 6 | items_seen_json | string | item_ids identified in the frame, e.g. `["tv_remote"]` |
| 7 | sharpness | f32 | frame sharpness score, same scale as `add_sighting` |

### Seed reducers (demo items and areas)
- `upsert_item(item_id, name, category, importance, aliases, attributes_json)`
- `upsert_area(area_id, name, room)`

### record_alert(type, item_id, message, channel, ts_ms, sent)
Appends one row to `alerts`. `item_id` `""` if none, `channel` `"spoken"` | `"carer"`, `ts_ms` f64,
`sent` bool (whether it actually went out).

### mark_alert_sent(id, sent)
`id` u64, `sent` bool. The backend's alert sender calls this once it has texted an alert.

### run_alert_checks_now(now_ms)
Runs the carer alert checks (section 5) immediately, for testing and the demo. `now_ms` f64 UTC ms;
`0` = the server's current time. Also makes sure `check_alerts` is scheduled.

### start_alert_checks()
Makes sure `check_alerts` is scheduled every 60 s. Safe to call any number of times; the backend
calls it at startup. (`init` does the same on a brand-new database.)

### check_alerts (scheduled, private)
Called by Spacetime every 60 s from the `alert_schedule` row. Not callable by clients.

### set_spot_description(item_id, placed_ts_ms, description)
Super VL's one-sentence description of the spot ("on the desk between the lamp and the water
bottles"). `placed_ts_ms` f64 must equal the item's current `item_state.last_placed_ts_ms`, or the
call does nothing: a description that arrives after the item has moved again is thrown away rather
than attached to the wrong spot.

### set_scene(ts_ms, outdoors)
Super VL's indoors/outdoors verdict for a kept frame, about once a minute. `ts_ms` f64, `outdoors`
bool. Spacetime keeps `status.outdoors_since` (the start of the current outdoor stretch, 0 when
indoors); `check_alerts` raises `left_house` once it has been outdoors for `OUTDOORS_MIN_MS`.

### report_possible_fall(ts_ms)
Called by the backend's fall check once Super VL has agreed (section 5). `ts_ms` f64 UTC ms (`0` =
server time). Writes a carer alert, type `possible_fall`, unless there was one within
`FALL_ALERT_EVERY_MS` (30 min); otherwise does nothing.

### request_carer_alert(type, message)
The agent's `send_carer_alert` tool (section 4). `type` must be `"agent_request"`; `message` is
trimmed to 300 characters. Writes an unsent carer alert, type `agent_request`, unless one was
written in the last `AGENT_REQUEST_EVERY_MS` (10 min), or the type is wrong or the message empty;
then it writes nothing (it doesn't fail, so the caller reads `alerts` back to see which). The
sender loop texts it like any carer alert.

### reset_memory()
Clears `sightings`, `item_state`, `events`, `routines`, `alerts`, `tracking` and `status`. Keeps
`items`, `areas` and the alert schedule. For between demo runs.

## 3. Spacetime tables

- `items`: item_id (pk), name, category, importance, aliases (list of strings), attributes (JSON).
  No owner.
- `areas`: area_id (pk), name, room.
- `sightings`: id (auto), plus every `add_sighting` argument. Append-only, never edited.
- `item_state`: the current belief about each item, the last place it was seen. item_id (pk), state
  (`"placed"` | `"unknown"`), area_id (indexed), furniture, rel_pos_json, last_placed_ts_ms,
  thumb_b64, spot_description (from Super VL), last_seen_ts_ms, confidence, candidates_json
  (alternatives when ambiguous).
- `events`: id (auto), item_id, type (`"placed"` | `"used"`), ts_ms, from_json, to_json.
- `routines`: item_id, hour (0 to 23), use_count. How often each item gets used at each hour of the
  day.
- `alerts`: id (auto), type (`pill_reminder`, `pills_not_taken`, `no_activity`, `left_house`,
  `possible_fall`, `agent_request`), item_id (`""` if none), message, channel (`"spoken"` = said on
  Nemo's speaker | `"carer"` = texted),
  ts_ms, sent (bool).
- `tracking` (**private**, not public): the rules' working memory, one row per item. item_id (pk),
  streak_count (sightings in a row in the same area and furniture), streak_area_id,
  streak_furniture, missing_since_ts (optional: when a sharp frame showed the item's furniture
  without it).
- `status` (**private**): key (pk), ts_ms. `"last_frame"` = when `add_frame` was last called (any
  kept frame, sharp or not), used by the no_activity check. `"outdoors_since"` = when the current
  outdoor stretch began (0 = indoors), set by `set_scene`, used by the left_house check.
- `alert_schedule` (**private**): scheduled_id (pk), scheduled_at. One repeating row that runs
  `check_alerts` every 60 s.

`item_state` rows are created the first time an item is confirmed. A `placed` event's
`from_json` / `to_json` are `{"area_id", "furniture", "rel_pos"}`, with `from_json` `""` the first
time. A `used` event's `from_json` is `{"missing_since_ts"}` and `to_json` is the spot.

### Constants (top of the module)
| name | value | meaning |
|---|---|---|
| CONFIRM_FRAMES | 2 | sightings in a row in the same area and furniture before `item_state` changes |
| FRAME_SHARP_MIN | 100 | `add_frame` sharpness must be above this for a spot to count as clearly in view |
| IMPORTANT | 3 | importance at which "used" is tracked (the pill bottle, item_id `pill_box`) |
| LOCAL_UTC_OFFSET_HOURS | -6 | local hour for `routines` (Dallas, CST) |
| OUTDOORS_MIN_MS | 120000 | outdoors for this long (2 min) = left the house |

### Logic that must live in reducers (Spacetime track rule)
- **Last seen** (`add_sighting`): store the raw sighting first.
  - **Ambiguous** (`item_id` `""`, e.g. a small DINOv2 margin): stop, change nothing.
  - Otherwise count sightings in a row in the same area and furniture. Once that reaches
    `CONFIRM_FRAMES`, update `item_state` (state `"placed"`, area_id, furniture, rel_pos_json,
    last_placed_ts_ms, thumb_b64, confidence = det_conf x area_conf (det_conf alone while area_id is ""), candidates_json,
    last_seen_ts_ms). This is a noise filter: one stray sighting somewhere else changes nothing.
  - Write a `placed` event only when the area or furniture actually changes.
- **Missing from its furniture** (`add_frame`): if an important item (importance 3) is placed on
  furniture X in area A, and a frame in area A has X in view, sharpness above `FRAME_SHARP_MIN`,
  and that item isn't in `items_seen`, set `missing_since_ts` in `tracking`. Don't change
  `item_state`: not seen doesn't change where it is. Looking the other way, or a blurry frame,
  changes nothing.
- **Used** (`add_sighting`): when an important item with `missing_since_ts` set is confirmed back
  on the same furniture in the same area (anywhere on it, not the exact spot), write a `used`
  event, +1 to `routines` for the local hour, and clear `missing_since_ts`. If it's confirmed
  somewhere else instead, that's a `placed` event and `missing_since_ts` is cleared. It's a sign
  the pills were taken, not proof: no medical claims.

### Super VL (built, `backend/vl.py`)
Nemotron 3.5 Super VL (`NEMOTRON_VL_MODEL`, OpenRouter `OPENROUTER_VL_MODEL` as fallback) never sits
on the frame loop or the question path. One background thread makes one call at a time from a
short queue (4 jobs; when it's full a job is dropped, not queued), thinking off, short answers,
`VL_TIMEOUT_S`. Images are small crops (448 to 640 px, 15 to 30 KB), with a green box drawn round
the item when the crop could show several things. Calls take about 1 to 2 s. `SUPER_VL=off` turns
all of it off; nothing else changes.

After each kept frame (`vl.after_frame`), in the background:
- **Second opinion** (`VL_SECOND_OPINION`): for a sighting vision left unsure (empty item_id with
  candidates), biggest box first, at most 2 per frame, boxes under 80 px skipped. Super VL is shown
  the crop and every tracked item's name (most likely first: YOLOE's wording, DINOv2's guesses,
  then the rest) plus "none of them" and "unsure". A pick only counts if it agrees with YOLOE's
  wording or DINOv2's top guess, OR Super VL gave the same pick for a box with the same YOLOE
  wording on a different frame within 20 s. It is then reported again as a normal `add_sighting`
  with that item_id and margin 1.0, so the placement rules (CONFIRM_FRAMES and all) still decide.
  Nothing is written directly.
- **Pill box fallback**: if Super VL says unsure (or can't be asked: box under 80 px, or the call
  failed) and YOLOE's wording was a pill-box wording with confidence at least 0.30 (the detection
  floor is 0.20), the sighting is reported as `pill_box` the same way. Only the pill bottle: it's the
  item the reminders and carer alerts depend on, and nothing else we track looks like one. The
  2-in-a-row rule still applies, so one such frame changes nothing.
- **Spot description**: when a sighting from this frame made Spacetime place an item
  (`item_state.last_placed_ts_ms` equals the frame's `ts_ms`) and the description is empty, Super
  VL describes the spot in one sentence, told which furniture Spacetime says it's on, and
  `set_spot_description` stores it. `where_is` returns it as `spot_description`.
- **Scene check** (`VL_SCENE_CHECK`, every `VL_SCENE_EVERY_S` = 60 s): indoors or outdoors from the
  newest kept frame, whole frame at 512 px, written with `set_scene`.

## 4. Agent tools (Nemotron 3.5 Lightning, OpenAI-style function calling)

`backend/agent.py`: max 5 model calls per question, thinking off, NVIDIA API first then
OpenRouter.

- `find_item(name)` -> `{"item_id", "name", "where"}`, where `where` is the `where_is` result for
  that item (so a plain "where's my X?" needs one tool call, not two), or `{"candidates": [...]}` if
  several match, or `{"found": false, "tracked_items": [...]}`. Matches items.name, item_id,
  aliases, then attributes.
- `where_is(item_id)` -> spot (a ready-to-say phrase such as "on the sofa by the couch"), area
  name, furniture, spot_description (Super VL's sentence, `""` if none yet), minutes_ago,
  confidence, candidates. For a tracked item Nemo hasn't spotted yet:
  `{"tracked": true, "seen": false, "note"}` (answer "I haven't seen your keys yet", not "I don't
  keep track of that"). For one seen with no area and no furniture:
  `{"seen": true, "place_known": false, "minutes_ago", "note"}` ("I saw it about N minutes ago, but
  I couldn't tell where").
- `item_history(item_id)` -> the 10 newest events (type, minutes_ago, to) and `uses_by_hour` from
  `routines`.
- `look_at_snapshot(item_id, question)` -> `{"item_id", "minutes_ago", "answer"}`: Nemotron 3.5
  Super VL looks at the newest saved frame that shows the item (a 640 px crop with the item boxed;
  the thumbnail in `item_state` if no frame is left on disk, with a `note`) and answers the question
  in one sentence, only from what it can see. `{"available": false, "reason"}` when Super VL is off,
  there is no photo, or it did not answer within 8 s. The agent is told to use it only when memory
  is not enough: confidence under 0.5, look-alike candidates, or the wearer asks for a detail (what
  it is next to, what colour, open or closed). It adds about 1 s to that answer. Measured on the
  desk frames: "is my wallet open or closed, and what colour is it?" -> "Your wallet is black and
  closed."

- `send_carer_alert(reason, message)` -> `{"requested": true, "message", "say"}` or
  `{"requested": false, "too_soon": true, "minutes_since_last", "say"}`. The agent only requests:
  the tool calls Spacetime's `request_carer_alert("agent_request", message)`, which records an
  unsent carer alert (at most one every 10 minutes), and the backend's sender loop texts it, so
  `CARER_ALERTS` still decides whether anything goes out. The tool never calls Photon. `reason` is
  `asked_to_pass_on` or `fallen_hurt_or_needs_help` (logged). The text always starts "Nemo here."
  and is one short sentence in the wearer's words where possible, e.g. "Nemo here. They asked me to
  tell you they're okay." `say` is the exact spoken reply ("Okay, I've let your carer know.", or
  that a message already went a few minutes ago), so the agent never claims a text that wasn't
  sent. Used only when the wearer asks to tell their carer or family something, or says they've
  fallen, are hurt or need help; never on the agent's own initiative. Questions that ask to pass
  something on ("tell", "let them know", ...; "tell me" doesn't count) skip the prefetch and get a
  one-line hint to use the tool. Measured: 15 of 15 requests sent (5 wordings, 3 times each), 0 of
  5 other questions ("can you tell me where my keys are?", "what's my daughter's name?", ...).

Carer alerts the agent didn't ask for (pills, no activity, left the house, possible fall) are
decided in Spacetime and sent by the sender loop (section 5).

Guardrails (system prompt): Nemo only answers from its tools. It never invents names, family,
health, places or times, says it's a device with no family or life of its own, and answers
anything outside its two jobs (finding things, passing a message to the carer) with "I'm sorry, I can't help with that. I can help you find your
things, like your keys or glasses."

Speed-ups:
- **Prefetch:** if the question names exactly one tracked item (its name, id or an alias, as whole
  words), the backend runs `find_item` for it before the first model call (plus `item_history` for
  importance-3 items, the pills) and puts the results in the conversation as tool calls. A plain
  "where's my X?" then needs one Nemotron call instead of two. Other questions use the normal loop.
- `items` and `areas` are cached in memory for 60 s; `item_state` is always read fresh.
- Whisper is warmed up at startup, so the first question isn't slower than the rest.
- `/ask` pauses vision (new frames are skipped) while it's answering, so speech to text and the
  agent get the CPU.

## 5. Alerts

### Backend -> notifier (carer texts)
`notifier/` is a small Bun + TypeScript service using Photon's Spectrum SDK (`spectrum-ts`, iMessage
provider). It reads `SPECTRUM_PROJECT_ID`, `SPECTRUM_PROJECT_SECRET`, `CARER_PHONE` (E.164, e.g.
`+15551234567`) and `NOTIFIER_PORT` (default 8100) from the repo-root `.env`. One way only.

`POST http://127.0.0.1:{NOTIFIER_PORT}/alert`
- Body: `{"type": "pills_missed", "message": "..."}`
- Response: `200 {"ok": true}` once Photon accepts it (not a delivery receipt), or
  `502 {"ok": false, "error": "..."}`; `400` for a bad body.

Python: `backend/alerts.py`
- `notify(type, message)` -> `(ok, error)`: calls the notifier only, never raises.
- `send_carer_alert(type, message, item_id="")` -> `{"sent", "error", "ms"}`: calls the notifier
  AND writes the alert with `record_alert` (channel `"carer"`, sent true/false).

Photon free/pro plans use a shared line that only texts numbers that are BOTH added as **Users** in
the Photon dashboard AND have texted the shared line first (any message). Until then sends fail
with `PERMISSION_DENIED: Target not allowed for this project`. Business gives a dedicated line.

### Alerts decided in Spacetime (built)
Spacetime decides WHEN; the backend only delivers. Every message follows the brand word list: plain,
kind, a nudge to check in, no alarm words, no medical claims.

- `check_alerts` (every 60 s) and `run_alert_checks_now` write unsent rows to `alerts`. At most one
  per type and channel per local day, and never while an unsent one of that type exists.
- **pill_reminder** (channel `"spoken"`, item_id `pill_box`): the usual hour is the hour with the
  highest `use_count` in `routines` for the pill bottle, or `PILL_DUE_HOUR` if there's no routine
  yet. From the usual hour to `PILL_REMINDER_WINDOW_MIN` (15) after it, if there's no `used` event
  for the pill bottle today (local day): "Hi, it's Nemo. It's about the usual time for your pills."
  Said on Nemo's speaker. It always comes before the carer text below.
- **pills_not_taken** (channel `"carer"`, item_id `pill_box`): once it's past the usual hour +
  `PILL_GRACE_MIN` and still no `used` event today: "Nemo here. The pill bottle hasn't moved by its
  usual time. You may want to check in." plus, if it has been placed, "It was last seen on the
  desk." (furniture, and "by the <area>" when that's different).
- **no_activity** (item_id `""`): between `DAY_START_HOUR` and `DAY_END_HOUR` local, if there's been
  no `placed` or `used` event and no `add_frame` for `NO_ACTIVITY_MIN`, raise: "No activity seen for
  about N hours." Not raised if nothing has ever been seen (the device is probably off).
- **left_house**: `set_scene` (Super VL, once a minute) keeps `status.outdoors_since`. Once the
  wearer has been outdoors for `OUTDOORS_MIN_MS` (2 min), `check_alerts` writes a `left_house`
  alert ("It looks like they've left the house (outdoors for about N minutes)"). Coming back
  indoors resets the stretch.
- **possible_fall** (channel `"carer"`): raised by `report_possible_fall` (below), not by
  `check_alerts`: "Nemo here. Nemo has only seen the floor or the ceiling for about a minute. You
  may want to check in." At most one every 30 minutes.
- **agent_request** (channel `"carer"`): raised by `request_carer_alert` for the agent's
  `send_carer_alert` tool (section 4). At most one every 10 minutes.

| constant (top of the module) | value |
|---|---|
| ALERT_CHECK_EVERY_MS | 60000 |
| PILL_ITEM_ID | `pill_box` |
| PILL_DUE_HOUR | 9 (local) |
| PILL_GRACE_MIN | 60 |
| PILL_REMINDER_WINDOW_MIN | 15 |
| FALL_ALERT_EVERY_MS | 1800000 (30 min) |
| AGENT_REQUEST_EVERY_MS | 600000 (10 min) |
| DAY_START_HOUR, DAY_END_HOUR | 8, 21 (local) |
| NO_ACTIVITY_MIN | 180 |
| LOCAL_UTC_OFFSET_HOURS | -6 (local day and hour) |

Backend sender loop (`backend/alerts.py`, started with the FastAPI app, always running): every 5 s
it reads `SELECT * FROM alerts WHERE sent = false` and delivers each:
- channel `"carer"`: texted through the notifier, only while `CARER_ALERTS` is on;
- channel `"spoken"`: `speech.speak(message)` (the same voice as answers), then `POST {NEMO_URL}/play`
  (multipart `file`), whatever `CARER_ALERTS` says.
Then `mark_alert_sent(id, true)`. If delivery fails (notifier down, Nemo unreachable) the row stays
unsent and is retried next round, up to 3 tries per alert (counted in memory, so a backend restart
tries again; a spoken alert's WAV is made once and reused). An alert it gave up on stays unsent,
which blocks new alerts of that type until it's cleared.

**While the backend runs with `CARER_ALERTS=on` (the default), carer alerts are real texts to `CARER_PHONE`.** Set `CARER_ALERTS=off` in `.env` for testing: `notify()` then never contacts the notifier (so nothing is texted by any route) and carer rows are left unsent. Spoken alerts still play on Nemo. `reset_memory` clears all alerts, and turning `CARER_ALERTS` back on sends any carer alerts still waiting.

### Possible fall (built, `backend/fall.py`)
Nemo has no motion sensor, so this is camera only. `frames.handle()` passes every frame Nemo
returns (kept or dropped by vision) to `fall.observe()` first (a few ms: decoded at 1/4 size).
A frame is suspicious if it's very dark (mean grey under 25 of 255: lying face down or covered) or
a still, featureless view (grey spread under 12 and almost no change since the last frame: a floor
or ceiling). Normal frames of the dim hotel room never go below 45 and 25 (303 frames checked, none
suspicious). After `FALL_WINDOW_S` (45) of suspicious frames in a row, with no gap over 10 s (a
switched-off Nemo never counts), the newest frame goes once to Super VL in the `vl.py` worker:
"Does this look like a floor or ceiling seen by someone who has fallen, or a camera lying face
down? Answer yes or no." Yes -> `report_possible_fall(ts_ms)`. Any normal frame starts again.
`FALL_CHECK=off` turns it off; it needs `SUPER_VL` on to confirm.

`backend/demo_fall.py` shows it end to end for the video: by default it posts a dark frame to the
running backend's `/frame` once a second for `FALL_WINDOW_S` + 10 s (so the real check fires);
`--here` calls the same `fall.observe()` in-process with a fake clock (a few seconds). Measured
through the backend: 45 s of dark frames -> Super VL "Yes." in 0.9 s -> `possible_fall` alert.

## 6. Environment variables (see .env.example)

All URLs and keys come from `.env`. Nothing hardcoded. `.env.example` lists every setting with
its default. The demo `.env` on Liam's laptop changes these from the defaults:

| setting | demo value | why |
|---|---|---|
| `FRAME_SOURCE` | `pull` | the backend fetches Nemo's `/jpg` |
| `NEMO_JPG_URL`, `NEMO_URL` | `http://<Nemo's IP>/jpg`, `http://<Nemo's IP>` | shown on Nemo's OLED |
| `REFS_DIR` | `captures/grab/sorted` | the hotel set's reference photos |
| `SHARPNESS_GATE` | `12` | the hotel room is dim; 40 dropped almost every frame |
| `DETECT_IMGSZ`, `DETECT_CONF` | `1024`, `0.20` | small things like keys |
| `STT_MODEL` | `base.en` | faster than `small.en` on the laptop CPU |
| `TTS_PROVIDER` | `elevenlabs` | voice "Brian" |
| `CARER_ALERTS` | `off` | no real texts while testing |

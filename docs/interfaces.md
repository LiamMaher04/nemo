# Interfaces (the contracts between the four parts)

Agree these first so everyone can build in parallel. Change a contract only in this file, in the same
commit as the code change, and tell the team.

## 1. Device -> backend (HTTP, plain, same hotspot)

### POST /frame
- Body: raw JPEG bytes. `Content-Type: image/jpeg`.
- Headers: `X-Device-Id: nemo-a`, `X-Frame-Ts: <ms since device boot>` (optional).
- Response: `200 {"ok": true}`. Device ignores the body; it just keeps sending.
- Rate: start at 1 fps, up to ~4 if the hotspot and heat allow. Resolution 1280x960 or higher if
  stable (keys are tiny).

### POST /ask
- Body: raw audio of the button press. Default `audio/wav`, 16 kHz, mono, 16-bit PCM.
- Headers: `X-Device-Id`.
- Response: `200`, `Content-Type: audio/wav` (the spoken answer, for the speaker).
  Also header `X-Answer-Text: <the answer text>` so the device can show it on the OLED if useful.
- Fallback: `POST /ask_text` with `{"question": "where's my remote?"}` returns
  `{"answer": "...", "item_id": "...", "snapshot_url": "..."}` (used by the carer app Ask box and for
  testing without the device).

### POST /coverage
- Body: `{"device_id": "nemo-a", "state": "recording" | "paused" | "off", "reason": "button" | "boot" | "charging"}`
- Lets the agent say "I wasn't recording between 2 and 4".

## 2. Backend -> Spacetime (reducer calls over HTTP)

`POST {SPACETIME_URL}/v1/database/{SPACETIME_DB}/call/{reducer}`
Body is a JSON array of the reducer's arguments, in order.

### add_sighting
Python reports what it SAW. Spacetime decides what it MEANS (placed / carried / moved).

| arg | type | notes |
|---|---|---|
| ts_ms | u64 | UTC ms since epoch |
| frame_id | u64 | backend's frame counter |
| track_id | i32 | from the tracker, -1 if none |
| label | string | detector class, e.g. "eyeglasses" |
| det_conf | f32 | 0 to 1 |
| item_id | string | best match, "" if ambiguous or unknown |
| candidates_json | string | e.g. `[["reading_glasses",0.82],["sunglasses",0.79]]` |
| match_margin | f32 | top1 minus top2 similarity |
| room_id | string | "" if unknown |
| room_conf | f32 | |
| anchor_id | string | e.g. "coffee_table", "" if none |
| relation | string | "on", "next_to", "in", "" |
| bbox_json | string | `[x, y, w, h]` in pixels of the full frame |
| in_hand | bool | item box overlaps a hand box |
| thumb_b64 | string | small JPEG thumbnail (~160 px wide), base64. Faces blurred. |

### set_coverage(device_id: string, state: string, reason: string, ts_ms: u64)

### Setup reducers (called from the carer app)
- `upsert_item(item_id, display_name, aliases_json, detector_prompt, importance, is_container)`
- `upsert_room(room_id, name, aliases_json)`
- `upsert_anchor(anchor_id, room_id, name)`

## 3. Spacetime tables (first version, grow from here)

- `items`: item_id (pk), display_name, aliases_json, detector_prompt, importance, is_container
- `rooms`: room_id (pk), name, aliases_json
- `anchors`: anchor_id (pk), room_id, name
- `sightings`: id (auto), all add_sighting args. Append-only, never edited.
- `item_state`: item_id (pk), state ("placed" | "carried" | "in_container" | "unknown"),
  last_placed_room, last_placed_anchor, last_placed_relation, last_placed_ts_ms, last_placed_thumb_b64,
  last_seen_room, last_seen_ts_ms, confidence, alternatives_json
- `events`: id, item_id, type ("picked_up" | "placed" | "moved"), ts_ms, from_json, to_json
- `coverage`: id, device_id, state, reason, ts_ms
- `alerts`: id, item_id, type, message, ts_ms, acknowledged

### Logic that must live in reducers (Spacetime track rule)
- **Stationary rule:** an item counts as placed after N (start with 3) consecutive sightings with
  `in_hand = false` in the same room and anchor (or bbox centre within a tolerance). Then update
  `item_state` and write a `placed` event.
- `in_hand = true` -> state "carried", update last_seen, do NOT overwrite last_placed.
- Ambiguous sightings (item_id "") are stored but don't change item_state.
- Stretch: scheduled reducer that fades confidence, and one that raises an alert if an important item
  hasn't moved by a set time.

### Lookups the agent and app use
- `where_is(item_id)`: item_state row plus the last few sightings. Can be a reducer that writes to a
  `queries` table, or the agent reads item_state via SQL / subscription. Check Spacetime docs for the
  cleanest way to read from Python (SQL endpoint).

## 4. Agent tools (Nemotron, OpenAI-style function calling)

- `resolve_item(name)` -> item_id or a clarifying question (aliases: "specs", "clicker")
- `where_is(item_id)` -> location, time, confidence, snapshot
- `sighting_history(item_id, since)` -> recent sightings
- `coverage_gaps(since)` -> times the device wasn't recording
- `describe_snapshot(item_id)` -> Nemotron VL description of the last snapshot
- `notify_carer(message)` -> writes to `alerts`, shows in the app
- `speak(text)` -> TTS

## 5. Environment variables (see .env.example)

All URLs and keys come from `.env`. Nothing hardcoded.

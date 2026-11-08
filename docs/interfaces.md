# Interfaces (the contracts between the parts)

Agree these first so everyone can build in parallel. Change a contract only in this file, in the same
commit as the code change, and tell the team.

## 1. Device -> backend (HTTP, plain, same hotspot)

### POST /frame
- Body: raw JPEG bytes. `Content-Type: image/jpeg`.
- Headers: `X-Device-Id: nemo-a`, `X-Frame-Ts: <ms since device boot>` (optional).
- Response: `200 {"ok": true}`. The device ignores the body; it just keeps sending.
- The device captures about 5 to 10 frames a second and sends only the sharpest one each second.
- Resolution 1280 px wide or more (keys are tiny).
- The backend also drops blurry and near-duplicate frames before running any models.

### POST /ask
- The wearer holds the button and asks out loud. The device records while the button is held.
- Body: raw audio. `audio/wav`, 16 kHz, mono, 16-bit PCM.
- Headers: `X-Device-Id`.
- Backend: speech to text (faster-whisper; also test Nemotron 3 Nano Omni) -> agent -> text to
  speech.
- Response: `200`, `Content-Type: audio/wav` (the spoken answer, played on Nemo's speaker).

### POST /ask_text
- Text in, text out, for testing the agent without the device (no speech).
- Body: `{"question": "where's my remote?"}`
- Response: `200 {"answer": "...", "tool_calls": [{"name", "args", "result", "ms"}, ...]}`.
  `503` if no model provider could answer.

### GET /say
- The device polls this every few seconds for anything to say (reminders).
- Headers: `X-Device-Id`.
- Response: `200`, `Content-Type: audio/wav` if there's something to play, otherwise `204` with no
  body.

The OLED only ever shows eyes (awake when on, closed when off). Nothing from the backend goes on it.

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

### reset_memory()
Clears `sightings`, `item_state`, `events`, `routines`, `alerts` and `tracking`. Keeps `items` and
`areas`. For between demo runs.

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
- `alerts`: id (auto), type, item_id (`""` if none), message, channel (`"spoken"` | `"carer"`),
  ts_ms, sent (bool).
- `tracking` (**private**, not public): the rules' working memory, one row per item. item_id (pk),
  streak_count (sightings in a row in the same area and furniture), streak_area_id,
  streak_furniture, missing_since_ts (optional: when a sharp frame showed the item's furniture
  without it).

`item_state` rows are created the first time an item is confirmed. A `placed` event's
`from_json` / `to_json` are `{"area_id", "furniture", "rel_pos"}`, with `from_json` `""` the first
time. A `used` event's `from_json` is `{"missing_since_ts"}` and `to_json` is the spot.

### Constants (top of the module)
| name | value | meaning |
|---|---|---|
| CONFIRM_FRAMES | 2 | sightings in a row in the same area and furniture before `item_state` changes |
| FRAME_SHARP_MIN | 100 | `add_frame` sharpness must be above this for a spot to count as clearly in view |
| IMPORTANT | 3 | importance at which "used" is tracked (the pill box) |
| LOCAL_UTC_OFFSET_HOURS | -6 | local hour for `routines` (Dallas, CST) |

### Logic that must live in reducers (Spacetime track rule)
- **Last seen** (`add_sighting`): store the raw sighting first.
  - **Ambiguous** (`item_id` `""`, e.g. a small DINOv2 margin): stop, change nothing.
  - Otherwise count sightings in a row in the same area and furniture. Once that reaches
    `CONFIRM_FRAMES`, update `item_state` (state `"placed"`, area_id, furniture, rel_pos_json,
    last_placed_ts_ms, thumb_b64, confidence = det_conf x area_conf, candidates_json,
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

### Still to define (by build step)
- Step 6: how the Super VL spot description gets written into `item_state`.
- Step 7: how the outdoor check and the fall check reach Spacetime and raise `alerts`.
- Step 8: how reminders are picked from `routines` and queued for `GET /say`.

## 4. Agent tools (Nemotron 3.5 Lightning, OpenAI-style function calling)

Built so far (`backend/agent.py`, max 5 model calls per question, thinking off, NVIDIA API first
then OpenRouter):

- `find_item(name)` -> `{"item_id", "name"}`, or `{"candidates": [...]}` if several match, or
  `{"found": false, "tracked_items": [...]}`. Matches items.name, item_id, aliases, then attributes.
- `where_is(item_id)` -> `{"seen": false}`, or area name, room, furniture, spot_description,
  minutes_ago, confidence, candidates.
- `item_history(item_id)` -> the 10 newest events (type, minutes_ago, to) and `uses_by_hour` from
  `routines`.

Still to build:
- `look_at_snapshot(item_id)` -> Nemotron 3.5 Super VL looks at the latest snapshot, to double-check
  a location or confirm a fall.
- `send_carer_alert(message)` -> sends an iMessage/SMS through Photon (Spectrum TypeScript SDK) and
  writes the row to `alerts`. One way only.

## 5. Alerts

- **Spoken to the wearer** (through `GET /say`): reminders, e.g. around the usual pill time.
- **Texted to the carer** (through Photon):
  - left the house (Super VL outdoor check, once a minute);
  - pills not taken by the usual time;
  - possible fall: a jolt, then black or a fixed floor/ceiling view for 30 to 60 s, confirmed by
    Super VL;
  - no activity for hours during the daytime.

## 6. Environment variables (see .env.example)

All URLs and keys come from `.env`. Nothing hardcoded.

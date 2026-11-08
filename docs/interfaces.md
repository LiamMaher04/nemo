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
Python reports what it SAW. Spacetime decides what it MEANS (placed / carried / used / moved).

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
| 12 | moves_with_background | f32 | 0 to 1. 1 = resting, 0 = carried by the wearer |
| 13 | sharpness | f32 | frame sharpness score |
| 14 | bbox_json | string | `[x, y, w, h]` in pixels of the full frame |
| 15 | thumb_b64 | string | small JPEG thumbnail, base64. Faces blurred. |

Furniture is only ever a place, never an item: it fills `furniture`, never `item_id` or `label`.

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
- `item_state`: the current belief about each item. item_id (pk), state
  (`"placed"` | `"carried"` | `"unknown"`), area_id (indexed), furniture, rel_pos_json,
  last_placed_ts_ms, thumb_b64, spot_description (from Super VL), last_seen_ts_ms, confidence,
  candidates_json (alternatives when ambiguous).
- `events`: id (auto), item_id, type (`"placed"` | `"picked_up"` | `"moved"` | `"used"`), ts_ms,
  from_json, to_json.
- `routines`: item_id, hour (0 to 23), use_count. How often each item gets used at each hour of the
  day.
- `alerts`: id (auto), type, item_id (`""` if none), message, channel (`"spoken"` | `"carer"`),
  ts_ms, sent (bool).
- `tracking` (**private**, not public): the rules' working memory between sightings, one row per
  item. item_id (pk), streak_count, streak_first_ts_ms, streak_area_id, streak_furniture,
  streak_first_cx, streak_first_cy (bbox centre at the start of the streak), streak_moved_px
  (furthest the bbox centre has moved during the streak), carried_since_ts_ms (optional),
  was_carried_since_last_placed (bool).

`item_state` rows are created with state `"unknown"` the first time an item is identified.
Event `from_json` / `to_json` are `{"area_id", "furniture", "rel_pos"}`, `""` when there was no
earlier spot, and `{"state": "carried"}` as the `to_json` of `picked_up`.

### Constants (top of the module)
| name | value | meaning |
|---|---|---|
| STATIONARY_FRAMES | 3 | resting sightings in the same spot before "placed" can commit |
| RESTING | 0.7 | `moves_with_background` at or above this = resting with the room |
| CARRIED | 0.3 | `moves_with_background` at or below this = carried |
| CARRIED_MIN_MS | 2000 | carried this long before it counts as picked up |
| CAMERA_MOVED_PX | 60 | bbox centre shift during a streak that means the wearer moved |
| LOCAL_UTC_OFFSET_HOURS | -6 | local hour for `routines` (Dallas, CST) |

### Logic that must live in reducers (Spacetime track rule)
`add_sighting` stores the raw sighting first, then:
- **Ambiguous** (`item_id` `""`, e.g. a small DINOv2 margin): stop, change nothing.
- Always update `last_seen_ts_ms` on `item_state` when the item is identified.
- No hand detection. Movement decides, through `moves_with_background`.
- **Carried** (`<= CARRIED`): start `carried_since_ts_ms` if not set. Once carried for
  `CARRIED_MIN_MS`: state `"carried"`, set `was_carried_since_last_placed`, write one `picked_up`
  event (not one per frame). Never overwrite the last placed spot. Reset the still streak.
- **Resting** (`>= RESTING`): clear `carried_since_ts_ms`. Grow the still streak if it's the same
  area and furniture, otherwise start a new one.
- **Placed** commits when the streak has `STATIONARY_FRAMES` or more, AND (the bbox centre moved at
  least `CAMERA_MOVED_PX` during the streak, meaning the camera moved but the item stayed with the
  room, OR `furniture` isn't `""`), AND it isn't already placed in that same area and furniture.
  Update `item_state` (state `"placed"`, area_id, furniture, rel_pos_json, last_placed_ts_ms,
  thumb_b64, confidence = det_conf x area_conf, candidates_json), then write:
  - carried since last placed: a `placed` event; if the item's importance is 3, also a **used**
    event and +1 to `routines` for the local hour;
  - not carried, and previously placed somewhere else: a **moved** event;
  - otherwise (first time): a `placed` event.
  Then reset `was_carried_since_last_placed`.
- **In between** (between `CARRIED` and `RESTING`, e.g. held while sitting still): only
  `last_seen_ts_ms` changes.
- **Not seen is not moved,** unless its spot was clearly in view.

### Still to define (by build step)
- Step 6: how the Super VL spot description gets written into `item_state`.
- Step 7: how the outdoor check and the fall check reach Spacetime and raise `alerts`.
- Step 8: how reminders are picked from `routines` and queued for `GET /say`.

## 4. Agent tools (Nemotron 3.5 Lightning, OpenAI-style function calling)

- `find_item(name)` -> item_id, using names and aliases, or a clarifying question if it's ambiguous.
- `where_is(item_id)` -> area, furniture, position, time, confidence.
- `item_history(item_id, since)` -> recent events and sightings.
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

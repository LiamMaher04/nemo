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

### Logic that must live in reducers (Spacetime track rule)
- No hand detection. Movement decides, through `moves_with_background`:
  - moves with the background = resting somewhere;
  - fixed to the camera while the background moves = carried by the wearer.
- **Placed:** still with the room for several frames (`STATIONARY_FRAMES`), committed only after the
  wearer has moved away. Update `item_state`, write a `placed` event.
- **Carried:** fixed to the camera for about 2 s. State `"carried"`; don't overwrite the last placed
  spot. Write a `picked_up` event.
- **Used:** an important item is carried, then put down again. Write a `used` event and add one to
  `routines` for that hour.
- **Moved:** the item turns up somewhere new without having been carried by the wearer. Write a
  `moved` event.
- **Not seen is not moved,** unless its spot was clearly in view.
- **Small DINOv2 margin:** store both candidates in the sighting, change neither item's state.

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

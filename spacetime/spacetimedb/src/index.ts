// Nemo memory module, as in docs/interfaces.md.
// add_sighting stores the raw sighting, then decides placed / carried / used / moved here.

import {
  CaseConversionPolicy,
  schema,
  table,
  t,
  type InferSchema,
  type ReducerCtx,
} from 'spacetimedb/server';

// ---- Placement rule constants ----
const STATIONARY_FRAMES = 3; // resting sightings in the same spot before "placed" can commit
const RESTING = 0.7; // moves_with_background at or above this = resting with the room
const CARRIED = 0.3; // moves_with_background at or below this = fixed to the camera (carried)
const CARRIED_MIN_MS = 2000; // carried this long before it counts as picked up
const CAMERA_MOVED_PX = 60; // bbox centre shift during a streak that means the wearer moved
const LOCAL_UTC_OFFSET_HOURS = -6; // Dallas (CST) for the routines hour

// What can be tracked. Seeded for the demo.
const items = table(
  { name: 'items', public: true },
  {
    item_id: t.string().primaryKey(),
    name: t.string(),
    category: t.string(),
    importance: t.u8(),
    aliases: t.array(t.string()),
    attributes: t.string(), // JSON
  }
);

// Places the wearer can be, matched by DINOv2 against pre-recorded clips.
const areas = table(
  { name: 'areas', public: true },
  {
    area_id: t.string().primaryKey(),
    name: t.string(),
    room: t.string(),
  }
);

// Everything the backend saw. Append-only, never edited.
const sightings = table(
  { name: 'sightings', public: true },
  {
    id: t.u64().primaryKey().autoInc(),
    ts_ms: t.f64(),
    frame_id: t.f64(),
    area_id: t.string(),
    area_conf: t.f32(),
    label: t.string(),
    det_conf: t.f32(),
    item_id: t.string(),
    candidates_json: t.string(),
    match_margin: t.f32(),
    furniture: t.string(),
    rel_pos_json: t.string(),
    moves_with_background: t.f32(),
    sharpness: t.f32(),
    bbox_json: t.string(),
    thumb_b64: t.string(),
  }
);

// The current belief about each item.
const item_state = table(
  { name: 'item_state', public: true },
  {
    item_id: t.string().primaryKey(),
    state: t.string(), // "placed" | "carried" | "unknown"
    area_id: t.string().index('btree'),
    furniture: t.string(),
    rel_pos_json: t.string(),
    last_placed_ts_ms: t.f64(),
    thumb_b64: t.string(),
    spot_description: t.string(),
    last_seen_ts_ms: t.f64(),
    confidence: t.f32(),
    candidates_json: t.string(),
  }
);

const events = table(
  { name: 'events', public: true },
  {
    id: t.u64().primaryKey().autoInc(),
    item_id: t.string(),
    type: t.string(), // "placed" | "picked_up" | "moved" | "used"
    ts_ms: t.f64(),
    from_json: t.string(),
    to_json: t.string(),
  }
);

// How often each item gets used at each hour of the day.
const routines = table(
  {
    name: 'routines',
    public: true,
    indexes: [{ accessor: 'by_item_hour', algorithm: 'btree', columns: ['item_id', 'hour'] }],
  },
  {
    id: t.u64().primaryKey().autoInc(),
    item_id: t.string(),
    hour: t.u8(), // 0 to 23
    use_count: t.u32(),
  }
);

const alerts = table(
  { name: 'alerts', public: true },
  {
    id: t.u64().primaryKey().autoInc(),
    type: t.string(),
    item_id: t.string(), // "" if none
    message: t.string(),
    channel: t.string(), // "spoken" | "carer"
    ts_ms: t.f64(),
    sent: t.bool(),
  }
);

// Private working memory for the rules, one row per item. Not public.
const tracking = table(
  { name: 'tracking' },
  {
    item_id: t.string().primaryKey(),
    streak_count: t.u32(), // resting sightings in a row in the same area + furniture
    streak_first_ts_ms: t.f64(),
    streak_area_id: t.string(),
    streak_furniture: t.string(),
    streak_first_cx: t.f64(), // bbox centre at the start of the streak
    streak_first_cy: t.f64(),
    streak_moved_px: t.f64(), // furthest the bbox centre has moved during the streak
    carried_since_ts_ms: t.option(t.f64()), // set while carried sightings keep coming
    was_carried_since_last_placed: t.bool(),
  }
);

// Names are already snake_case, so keep them exactly (the default would turn thumb_b64 into thumb_b_64).
const spacetimedb = schema(
  { items, areas, sightings, item_state, events, routines, alerts, tracking },
  { CASE_CONVERSION_POLICY: CaseConversionPolicy.None }
);
export default spacetimedb;

type Ctx = ReducerCtx<InferSchema<typeof spacetimedb>>;

function bboxCentre(bbox_json: string): [number, number] | null {
  try {
    const [x, y, w, h] = JSON.parse(bbox_json) as number[];
    if ([x, y, w, h].some(v => typeof v !== 'number')) return null;
    return [x + w / 2, y + h / 2];
  } catch {
    return null;
  }
}

function spotJson(s: { area_id: string; furniture: string; rel_pos_json: string }): string {
  return JSON.stringify({ area_id: s.area_id, furniture: s.furniture, rel_pos: s.rel_pos_json });
}

function localHour(ts_ms: number): number {
  const h = Math.floor(ts_ms / 3_600_000 + LOCAL_UTC_OFFSET_HOURS);
  return ((h % 24) + 24) % 24;
}

function addEvent(ctx: Ctx, item_id: string, type: string, ts_ms: number, from_json: string, to_json: string) {
  ctx.db.events.insert({ id: 0n, item_id, type, ts_ms, from_json, to_json });
}

function addRoutineUse(ctx: Ctx, item_id: string, hour: number) {
  const existing = [...ctx.db.routines.by_item_hour.filter([item_id, hour])][0];
  if (existing) {
    ctx.db.routines.id.update({ ...existing, use_count: existing.use_count + 1 });
  } else {
    ctx.db.routines.insert({ id: 0n, item_id, hour, use_count: 1 });
  }
}

// ---- Setup reducers ----

export const upsert_item = spacetimedb.reducer(
  {
    item_id: t.string(),
    name: t.string(),
    category: t.string(),
    importance: t.u8(),
    aliases: t.array(t.string()),
    attributes_json: t.string(),
  },
  (ctx, { item_id, name, category, importance, aliases, attributes_json }) => {
    const row = { item_id, name, category, importance, aliases, attributes: attributes_json };
    if (ctx.db.items.item_id.find(item_id)) {
      ctx.db.items.item_id.update(row);
    } else {
      ctx.db.items.insert(row);
    }
  }
);

export const upsert_area = spacetimedb.reducer(
  { area_id: t.string(), name: t.string(), room: t.string() },
  (ctx, { area_id, name, room }) => {
    const row = { area_id, name, room };
    if (ctx.db.areas.area_id.find(area_id)) {
      ctx.db.areas.area_id.update(row);
    } else {
      ctx.db.areas.insert(row);
    }
  }
);

// Argument order matches docs/interfaces.md. Python reports what it saw; this decides what it means.
export const add_sighting = spacetimedb.reducer(
  {
    ts_ms: t.f64(),
    frame_id: t.f64(),
    area_id: t.string(),
    area_conf: t.f32(),
    label: t.string(),
    det_conf: t.f32(),
    item_id: t.string(),
    candidates_json: t.string(),
    match_margin: t.f32(),
    furniture: t.string(),
    rel_pos_json: t.string(),
    moves_with_background: t.f32(),
    sharpness: t.f32(),
    bbox_json: t.string(),
    thumb_b64: t.string(),
  },
  (ctx, args) => {
    ctx.db.sightings.insert({ id: 0n, ...args });

    // Ambiguous or unknown: stored above, changes nothing.
    const id = args.item_id;
    if (id === '') return;

    const ts = args.ts_ms;

    // Current belief, created as "unknown" the first time an item is identified.
    let state =
      ctx.db.item_state.item_id.find(id) ??
      ctx.db.item_state.insert({
        item_id: id,
        state: 'unknown',
        area_id: '',
        furniture: '',
        rel_pos_json: '',
        last_placed_ts_ms: 0,
        thumb_b64: '',
        spot_description: '',
        last_seen_ts_ms: ts,
        confidence: 0,
        candidates_json: '',
      });
    state = { ...state, last_seen_ts_ms: ts };

    let track =
      ctx.db.tracking.item_id.find(id) ??
      ctx.db.tracking.insert({
        item_id: id,
        streak_count: 0,
        streak_first_ts_ms: 0,
        streak_area_id: '',
        streak_furniture: '',
        streak_first_cx: 0,
        streak_first_cy: 0,
        streak_moved_px: 0,
        carried_since_ts_ms: undefined,
        was_carried_since_last_placed: false,
      });

    const mwb = args.moves_with_background;

    if (mwb <= CARRIED) {
      // Carried: fixed to the camera while the background moves.
      const since = track.carried_since_ts_ms ?? ts;
      track = { ...track, carried_since_ts_ms: since, streak_count: 0, streak_moved_px: 0 };
      if (ts - since >= CARRIED_MIN_MS) {
        track = { ...track, was_carried_since_last_placed: true };
        if (state.state !== 'carried') {
          // One picked_up event per carry. The last placed spot is kept as it was.
          addEvent(ctx, id, 'picked_up', ts, spotJson(state), JSON.stringify({ state: 'carried' }));
          state = { ...state, state: 'carried' };
        }
      }
    } else if (mwb >= RESTING) {
      // Resting with the room: grow the still streak or start a new one.
      const centre = bboxCentre(args.bbox_json);
      track = { ...track, carried_since_ts_ms: undefined };
      const sameSpot =
        track.streak_count > 0 &&
        track.streak_area_id === args.area_id &&
        track.streak_furniture === args.furniture;
      if (sameSpot) {
        const moved = centre
          ? Math.hypot(centre[0] - track.streak_first_cx, centre[1] - track.streak_first_cy)
          : 0;
        track = {
          ...track,
          streak_count: track.streak_count + 1,
          streak_moved_px: Math.max(track.streak_moved_px, moved),
        };
      } else {
        track = {
          ...track,
          streak_count: 1,
          streak_first_ts_ms: ts,
          streak_area_id: args.area_id,
          streak_furniture: args.furniture,
          streak_first_cx: centre ? centre[0] : 0,
          streak_first_cy: centre ? centre[1] : 0,
          streak_moved_px: 0,
        };
      }

      // Commit "placed" once it's been still long enough and we know where it is: either the camera
      // moved while the item stayed with the room, or it's on a known piece of furniture.
      const alreadyHere =
        state.state === 'placed' && state.area_id === args.area_id && state.furniture === args.furniture;
      if (
        track.streak_count >= STATIONARY_FRAMES &&
        (track.streak_moved_px >= CAMERA_MOVED_PX || args.furniture !== '') &&
        !alreadyHere
      ) {
        const previouslyPlaced = state.last_placed_ts_ms > 0;
        const from = previouslyPlaced ? spotJson(state) : '';
        state = {
          ...state,
          state: 'placed',
          area_id: args.area_id,
          furniture: args.furniture,
          rel_pos_json: args.rel_pos_json,
          last_placed_ts_ms: ts,
          thumb_b64: args.thumb_b64,
          confidence: args.det_conf * args.area_conf,
          candidates_json: args.candidates_json,
        };
        const to = spotJson(state);

        if (track.was_carried_since_last_placed) {
          addEvent(ctx, id, 'placed', ts, from, to);
          const importance = ctx.db.items.item_id.find(id)?.importance ?? 0;
          if (importance === 3) {
            addEvent(ctx, id, 'used', ts, from, to);
            addRoutineUse(ctx, id, localHour(ts));
          }
        } else if (previouslyPlaced) {
          addEvent(ctx, id, 'moved', ts, from, to);
        } else {
          addEvent(ctx, id, 'placed', ts, from, to);
        }
        track = { ...track, was_carried_since_last_placed: false };
      }
    }
    // Between CARRIED and RESTING: only last_seen_ts_ms changes (set above).

    ctx.db.item_state.item_id.update(state);
    ctx.db.tracking.item_id.update(track);
  }
);

// Clears everything the device has taught the memory, keeping items and areas. For between demo runs.
export const reset_memory = spacetimedb.reducer(ctx => {
  for (const r of [...ctx.db.sightings.iter()]) ctx.db.sightings.id.delete(r.id);
  for (const r of [...ctx.db.item_state.iter()]) ctx.db.item_state.item_id.delete(r.item_id);
  for (const r of [...ctx.db.events.iter()]) ctx.db.events.id.delete(r.id);
  for (const r of [...ctx.db.routines.iter()]) ctx.db.routines.id.delete(r.id);
  for (const r of [...ctx.db.alerts.iter()]) ctx.db.alerts.id.delete(r.id);
  for (const r of [...ctx.db.tracking.iter()]) ctx.db.tracking.item_id.delete(r.item_id);
});

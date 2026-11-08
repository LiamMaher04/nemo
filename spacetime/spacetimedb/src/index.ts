// Nemo memory module, as in docs/interfaces.md.
// add_sighting keeps the last place each item was seen; add_frame notices when an important item is
// missing from its furniture, so seeing it back there counts as "used".

import {
  CaseConversionPolicy,
  schema,
  table,
  t,
  type InferSchema,
  type ReducerCtx,
} from 'spacetimedb/server';

// ---- Memory rule constants ----
const CONFIRM_FRAMES = 2; // same area + furniture this many sightings in a row before item_state changes
const FRAME_SHARP_MIN = 100; // add_frame sharpness must be above this to count a spot as clearly in view
const IMPORTANT = 3; // importance at which "used" is tracked (the pill box)
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
    sharpness: t.f32(),
    bbox_json: t.string(),
    thumb_b64: t.string(),
  }
);

// The current belief about each item: the last place it was seen.
const item_state = table(
  { name: 'item_state', public: true },
  {
    item_id: t.string().primaryKey(),
    state: t.string(), // "placed" | "unknown"
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
    type: t.string(), // "placed" | "used"
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
    streak_count: t.u32(), // sightings in a row in the same area + furniture
    streak_area_id: t.string(),
    streak_furniture: t.string(),
    missing_since_ts: t.option(t.f64()), // set when a sharp frame showed its furniture without it
  }
);

// Names are already snake_case, so keep them exactly (the default would turn thumb_b64 into thumb_b_64).
const spacetimedb = schema(
  { items, areas, sightings, item_state, events, routines, alerts, tracking },
  { CASE_CONVERSION_POLICY: CaseConversionPolicy.None }
);
export default spacetimedb;

type Ctx = ReducerCtx<InferSchema<typeof spacetimedb>>;

function spotJson(s: { area_id: string; furniture: string; rel_pos_json: string }): string {
  return JSON.stringify({ area_id: s.area_id, furniture: s.furniture, rel_pos: s.rel_pos_json });
}

function stringList(json: string): string[] {
  try {
    const v = JSON.parse(json);
    return Array.isArray(v) ? v.filter(x => typeof x === 'string') : [];
  } catch {
    return [];
  }
}

function localHour(ts_ms: number): number {
  const h = Math.floor(ts_ms / 3_600_000 + LOCAL_UTC_OFFSET_HOURS);
  return ((h % 24) + 24) % 24;
}

function importanceOf(ctx: Ctx, item_id: string): number {
  return ctx.db.items.item_id.find(item_id)?.importance ?? 0;
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

function getTracking(ctx: Ctx, item_id: string) {
  return (
    ctx.db.tracking.item_id.find(item_id) ??
    ctx.db.tracking.insert({
      item_id,
      streak_count: 0,
      streak_area_id: '',
      streak_furniture: '',
      missing_since_ts: undefined,
    })
  );
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

// ---- Vision reports ----

// One item seen in one frame. Argument order matches docs/interfaces.md.
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

    // Noise filter: count sightings in a row in the same area + furniture.
    let track = getTracking(ctx, id);
    const sameSpot =
      track.streak_count > 0 &&
      track.streak_area_id === args.area_id &&
      track.streak_furniture === args.furniture;
    track = sameSpot
      ? { ...track, streak_count: track.streak_count + 1 }
      : { ...track, streak_count: 1, streak_area_id: args.area_id, streak_furniture: args.furniture };

    if (track.streak_count >= CONFIRM_FRAMES) {
      const prev = ctx.db.item_state.item_id.find(id);
      const row = {
        item_id: id,
        state: 'placed',
        area_id: args.area_id,
        furniture: args.furniture,
        rel_pos_json: args.rel_pos_json,
        last_placed_ts_ms: ts,
        thumb_b64: args.thumb_b64,
        spot_description: prev?.spot_description ?? '',
        last_seen_ts_ms: ts,
        confidence: args.det_conf * args.area_conf,
        candidates_json: args.candidates_json,
      };
      const spotChanged = !prev || prev.area_id !== args.area_id || prev.furniture !== args.furniture;
      if (spotChanged) row.spot_description = ''; // describes the old spot, so drop it

      if (prev) {
        ctx.db.item_state.item_id.update(row);
      } else {
        ctx.db.item_state.insert(row);
      }

      if (spotChanged) {
        // A placed event only when the area or furniture actually changes.
        addEvent(ctx, id, 'placed', ts, prev ? spotJson(prev) : '', spotJson(row));
        track = { ...track, missing_since_ts: undefined }; // it's somewhere else now
      } else if (track.missing_since_ts !== undefined && importanceOf(ctx, id) >= IMPORTANT) {
        // Missing from its furniture in a sharp frame, now back on it: used.
        addEvent(
          ctx,
          id,
          'used',
          ts,
          JSON.stringify({ missing_since_ts: track.missing_since_ts }),
          spotJson(row)
        );
        addRoutineUse(ctx, id, localHour(ts));
        track = { ...track, missing_since_ts: undefined };
      }
    }

    ctx.db.tracking.item_id.update(track);
  }
);

// One kept frame, called once per frame by vision (after its sightings).
// Marks an important item missing if its furniture is clearly in view and the item isn't.
// Doesn't change item_state: not seen is not gone.
export const add_frame = spacetimedb.reducer(
  {
    ts_ms: t.f64(),
    frame_id: t.f64(),
    area_id: t.string(),
    area_conf: t.f32(),
    furniture_in_view_json: t.string(),
    items_seen_json: t.string(),
    sharpness: t.f32(),
  },
  (ctx, args) => {
    if (!(args.sharpness > FRAME_SHARP_MIN)) return;
    const furnitureInView = stringList(args.furniture_in_view_json);
    const itemsSeen = stringList(args.items_seen_json);

    for (const s of [...ctx.db.item_state.area_id.filter(args.area_id)]) {
      if (s.state !== 'placed' || s.furniture === '') continue;
      if (!furnitureInView.includes(s.furniture)) continue;
      if (itemsSeen.includes(s.item_id)) continue;
      if (importanceOf(ctx, s.item_id) < IMPORTANT) continue;

      const track = getTracking(ctx, s.item_id);
      if (track.missing_since_ts === undefined) {
        ctx.db.tracking.item_id.update({ ...track, missing_since_ts: args.ts_ms });
      }
    }
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

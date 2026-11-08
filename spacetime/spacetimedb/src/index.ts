// Nemo memory module. Tables and setup reducers only, as in docs/interfaces.md.
// No placement logic yet: add_sighting just stores the raw row.

import { CaseConversionPolicy, schema, table, t } from 'spacetimedb/server';

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

// Names are already snake_case, so keep them exactly (the default would turn thumb_b64 into thumb_b_64).
const spacetimedb = schema(
  { items, areas, sightings, item_state, events, routines, alerts },
  { CASE_CONVERSION_POLICY: CaseConversionPolicy.None }
);
export default spacetimedb;

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

// Argument order matches docs/interfaces.md. For now this only stores the raw sighting.
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
  }
);

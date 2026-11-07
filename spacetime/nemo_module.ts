// Nemo memory module for SpacetimeDB (TypeScript, spacetimedb/server).
//
// How to use: scaffold the project with
//   spacetime dev nemodb-g8356 --template basic-react --server maincloud
// (inside spacetime/), then replace the generated server module's src/index.ts with this file.
//
// The memory LOGIC lives here, not in Python (Spacetime track rule):
//   - add_sighting stores every raw sighting (append-only)
//   - the stationary rule decides when an item has been put down
//   - carried vs placed, events, confidence
// Python only reports what it saw. See docs/interfaces.md.

import { schema, table, t } from 'spacetimedb/server';

// How many consecutive still, not-in-hand sightings in the same place before we call it "placed".
const STATIONARY_FRAMES = 3;
// bbox centre grid (pixels) used as "same place" when there's no anchor.
const PLACE_GRID_PX = 120;

const spacetimedb = schema({
  items: table(
    { public: true },
    {
      item_id: t.string().primaryKey(),
      display_name: t.string(),
      aliases_json: t.string(), // e.g. ["specs","readers"]
      detector_prompt: t.string(), // e.g. "eyeglasses"
      importance: t.u8(), // 0 normal, 1 important (pill box), used for alerts
      is_container: t.bool(),
    }
  ),
  rooms: table(
    { public: true },
    {
      room_id: t.string().primaryKey(),
      name: t.string(),
      aliases_json: t.string(),
    }
  ),
  anchors: table(
    { public: true },
    {
      anchor_id: t.string().primaryKey(),
      room_id: t.string(),
      name: t.string(),
    }
  ),
  // Append-only raw observations. Never edited.
  sightings: table(
    { public: true },
    {
      id: t.u64().primaryKey().autoInc(),
      ts_ms: t.f64(),
      frame_id: t.f64(),
      track_id: t.i32(),
      label: t.string(),
      det_conf: t.f32(),
      item_id: t.string(),
      candidates_json: t.string(),
      match_margin: t.f32(),
      room_id: t.string(),
      room_conf: t.f32(),
      anchor_id: t.string(),
      relation: t.string(),
      bbox_json: t.string(),
      in_hand: t.bool(),
      // Thumbnails only kept on item_state (latest placement) to keep this table small.
    }
  ),
  // The current belief per item, recomputed from sightings by the reducers.
  item_state: table(
    { public: true },
    {
      item_id: t.string().primaryKey(),
      state: t.string(), // placed | carried | in_container | unknown
      last_placed_room: t.string(),
      last_placed_anchor: t.string(),
      last_placed_relation: t.string(),
      last_placed_ts_ms: t.f64(),
      last_placed_bbox_json: t.string(),
      last_placed_thumb_b64: t.string(),
      last_seen_room: t.string(),
      last_seen_ts_ms: t.f64(),
      confidence: t.f32(),
      alternatives_json: t.string(),
      // Stationary-rule working memory
      pending_place_key: t.string(),
      pending_count: t.u32(),
      pending_thumb_b64: t.string(),
    }
  ),
  events: table(
    { public: true },
    {
      id: t.u64().primaryKey().autoInc(),
      item_id: t.string(),
      type: t.string(), // picked_up | placed | moved
      ts_ms: t.f64(),
      from_json: t.string(),
      to_json: t.string(),
    }
  ),
  coverage: table(
    { public: true },
    {
      id: t.u64().primaryKey().autoInc(),
      device_id: t.string(),
      state: t.string(), // recording | paused | off
      reason: t.string(),
      ts_ms: t.f64(),
    }
  ),
  alerts: table(
    { public: true },
    {
      id: t.u64().primaryKey().autoInc(),
      item_id: t.string(),
      type: t.string(),
      message: t.string(),
      ts_ms: t.f64(),
      acknowledged: t.bool(),
    }
  ),
});
export default spacetimedb;

// ---------- helpers ----------

function placeKey(room_id: string, anchor_id: string, bbox_json: string): string {
  if (anchor_id) return `${room_id}|${anchor_id}`;
  try {
    const [x, y, w, h] = JSON.parse(bbox_json) as number[];
    const cx = Math.floor((x + w / 2) / PLACE_GRID_PX);
    const cy = Math.floor((y + h / 2) / PLACE_GRID_PX);
    return `${room_id}|grid:${cx},${cy}`;
  } catch {
    return `${room_id}|?`;
  }
}

function where(room: string, anchor: string, relation: string): string {
  return JSON.stringify({ room, anchor, relation });
}

function blankState(item_id: string) {
  return {
    item_id,
    state: 'unknown',
    last_placed_room: '',
    last_placed_anchor: '',
    last_placed_relation: '',
    last_placed_ts_ms: 0,
    last_placed_bbox_json: '',
    last_placed_thumb_b64: '',
    last_seen_room: '',
    last_seen_ts_ms: 0,
    confidence: 0,
    alternatives_json: '[]',
    pending_place_key: '',
    pending_count: 0,
    pending_thumb_b64: '',
  };
}

// ---------- setup reducers (carer app) ----------

export const upsert_item = spacetimedb.reducer(
  {
    item_id: t.string(),
    display_name: t.string(),
    aliases_json: t.string(),
    detector_prompt: t.string(),
    importance: t.u8(),
    is_container: t.bool(),
  },
  (ctx, row) => {
    if (ctx.db.items.item_id.find(row.item_id)) ctx.db.items.item_id.update(row);
    else ctx.db.items.insert(row);
  }
);

export const upsert_room = spacetimedb.reducer(
  { room_id: t.string(), name: t.string(), aliases_json: t.string() },
  (ctx, row) => {
    if (ctx.db.rooms.room_id.find(row.room_id)) ctx.db.rooms.room_id.update(row);
    else ctx.db.rooms.insert(row);
  }
);

export const upsert_anchor = spacetimedb.reducer(
  { anchor_id: t.string(), room_id: t.string(), name: t.string() },
  (ctx, row) => {
    if (ctx.db.anchors.anchor_id.find(row.anchor_id)) ctx.db.anchors.anchor_id.update(row);
    else ctx.db.anchors.insert(row);
  }
);

// ---------- the memory ----------

export const add_sighting = spacetimedb.reducer(
  {
    ts_ms: t.f64(),
    frame_id: t.f64(),
    track_id: t.i32(),
    label: t.string(),
    det_conf: t.f32(),
    item_id: t.string(),
    candidates_json: t.string(),
    match_margin: t.f32(),
    room_id: t.string(),
    room_conf: t.f32(),
    anchor_id: t.string(),
    relation: t.string(),
    bbox_json: t.string(),
    in_hand: t.bool(),
    thumb_b64: t.string(),
  },
  (ctx, s) => {
    const { thumb_b64, ...raw } = s;
    ctx.db.sightings.insert({ id: 0n, ...raw });

    // Ambiguous or unknown object: keep the evidence, don't change beliefs.
    if (!s.item_id) return;

    const prev = ctx.db.item_state.item_id.find(s.item_id);
    const st = prev ? { ...prev } : blankState(s.item_id);
    const conf = s.det_conf * Math.max(s.room_conf, 0.5);

    st.last_seen_room = s.room_id;
    st.last_seen_ts_ms = s.ts_ms;

    if (s.in_hand) {
      // Being carried: update last seen, never overwrite where it was last put down.
      if (st.state === 'placed') {
        ctx.db.events.insert({
          id: 0n,
          item_id: s.item_id,
          type: 'picked_up',
          ts_ms: s.ts_ms,
          from_json: where(st.last_placed_room, st.last_placed_anchor, st.last_placed_relation),
          to_json: '{}',
        });
      }
      st.state = 'carried';
      st.pending_place_key = '';
      st.pending_count = 0;
      st.pending_thumb_b64 = '';
    } else {
      // Stationary rule: N consecutive still sightings in the same place = put down.
      const key = placeKey(s.room_id, s.anchor_id, s.bbox_json);
      if (key === st.pending_place_key) st.pending_count += 1;
      else {
        st.pending_place_key = key;
        st.pending_count = 1;
      }
      if (thumb_b64) st.pending_thumb_b64 = thumb_b64;

      const lastKey = placeKey(st.last_placed_room, st.last_placed_anchor, st.last_placed_bbox_json);
      const alreadyThere = st.state === 'placed' && lastKey === key;

      if (st.pending_count >= STATIONARY_FRAMES && !alreadyThere) {
        const from = st.last_placed_room
          ? where(st.last_placed_room, st.last_placed_anchor, st.last_placed_relation)
          : '{}';
        st.state = 'placed';
        st.last_placed_room = s.room_id;
        st.last_placed_anchor = s.anchor_id;
        st.last_placed_relation = s.relation;
        st.last_placed_ts_ms = s.ts_ms;
        st.last_placed_bbox_json = s.bbox_json;
        st.last_placed_thumb_b64 = st.pending_thumb_b64;
        st.alternatives_json = s.candidates_json;
        ctx.db.events.insert({
          id: 0n,
          item_id: s.item_id,
          type: from === '{}' ? 'placed' : 'moved',
          ts_ms: s.ts_ms,
          from_json: from,
          to_json: where(s.room_id, s.anchor_id, s.relation),
        });
      }
      if (st.pending_count >= STATIONARY_FRAMES && !alreadyThere) {
        st.confidence = conf; // fresh placement
      } else if (alreadyThere) {
        // Seen again where we thought it was: refresh confidence.
        st.confidence = Math.min(1, Math.max(st.confidence, conf));
      }
    }

    if (prev) ctx.db.item_state.item_id.update(st);
    else ctx.db.item_state.insert(st);
  }
);

export const set_coverage = spacetimedb.reducer(
  { device_id: t.string(), state: t.string(), reason: t.string(), ts_ms: t.f64() },
  (ctx, c) => {
    ctx.db.coverage.insert({ id: 0n, ...c });
  }
);

// Called by the agent (notify_carer tool) or a proactive check.
export const raise_alert = spacetimedb.reducer(
  { item_id: t.string(), type: t.string(), message: t.string(), ts_ms: t.f64() },
  (ctx, a) => {
    ctx.db.alerts.insert({ id: 0n, ...a, acknowledged: false });
  }
);

export const ack_alert = spacetimedb.reducer({ id: t.u64() }, (ctx, { id }) => {
  const a = ctx.db.alerts.id.find(id);
  if (a) ctx.db.alerts.id.update({ ...a, acknowledged: true });
});

// Demo helper: wipe beliefs and history, keep items/rooms/anchors.
export const reset_memory = spacetimedb.reducer({}, ctx => {
  for (const r of ctx.db.sightings.iter()) ctx.db.sightings.id.delete(r.id);
  for (const r of ctx.db.events.iter()) ctx.db.events.id.delete(r.id);
  for (const r of ctx.db.item_state.iter()) ctx.db.item_state.item_id.delete(r.item_id);
  for (const r of ctx.db.alerts.iter()) ctx.db.alerts.id.delete(r.id);
});

// TODO (stretch, scheduled reducers): fade confidence over time; raise an alert when an important
// item (importance = 1, e.g. the pill box) hasn't been picked up by a set time.

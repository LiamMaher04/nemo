# spacetime

SpacetimeDB module (TypeScript) + React carer app. Database: `nemodb-g8356` on Maincloud.

## Setup (Windows PowerShell)

```
iwr https://windows.spacetimedb.com -useb | iex
spacetime login
cd spacetime
spacetime dev nemodb-g8356 --template basic-react --server maincloud
```
(If `basic-react` isn't a template name, `spacetime dev --help` lists them. Pick the plain React
TypeScript one, not the chat one.)

Then **replace the generated server module's `src/index.ts` with `nemo_module.ts`** from this folder.
`spacetime dev` republishes on save and regenerates the client bindings.

## Check it

```
spacetime sql nemodb-g8356 --server maincloud "SELECT * FROM item_state"
spacetime logs nemodb-g8356 --server maincloud
```
Then from the repo root: `python -m backend.fake_sighting seed` and `... place remote living_room sofa_arm`.

## What's in the module

- Tables: items, rooms, anchors, sightings (append-only), item_state (current belief), events,
  coverage, alerts.
- `add_sighting` holds the memory logic: 3 still, not-in-hand sightings in the same place = placed;
  in hand = carried (last placed spot kept); placed/moved/picked_up events; confidence.
- Setup: `upsert_item`, `upsert_room`, `upsert_anchor`. Also `set_coverage`, `raise_alert`,
  `ack_alert`, `reset_memory` (demo reset).
- Written against the current TypeScript module docs but not compiled yet. If `spacetime dev` errors,
  paste the error into Claude Code.

## Carer app (next)

Subscribe to `item_state`, `events` and `alerts`. Floor plan: one box per room, a pin per placed item
(anchor name + "x minutes ago"), tap for `last_placed_thumb_b64`. Plus a text Ask box that POSTs to
the backend's `/ask_text`.

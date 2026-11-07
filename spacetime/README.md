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

## Live view (core) and carer app (extended scope)

Core: one plain page subscribed to `item_state` showing item, room, spot and "x minutes ago",
updating live. That's what proves Spacetime is doing the work during the demo.

Extended, only if time allows: floor plan with pins, snapshots (`last_placed_thumb_b64`), alerts,
setup screens, text Ask box posting to `/ask_text`.

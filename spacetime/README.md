# spacetime

SpacetimeDB module (TypeScript) for the database `nemodb-g8356` on Maincloud.

- Tables and reducers: `docs/interfaces.md` sections 2 and 3. Alerts: section 5.
- The memory logic lives in reducers, not in Python:
  - **last seen:** `add_sighting` updates `item_state` once an item is seen `CONFIRM_FRAMES` (2)
    times in a row in the same area and furniture;
  - **add_frame:** vision reports each kept frame, so a sharp frame showing an important item's
    furniture without the item marks it missing;
  - **used:** that item seen back on the same furniture in the same area;
  - **carer alerts:** `check_alerts` runs every 60 s and raises pills_not_taken, no_activity and
    left_house (from `set_scene`, Super VL's indoors check);
  - `set_spot_description` only attaches a description to the spot it was written for.
- Publish from this folder: `spacetime publish nemodb-g8356 -s maincloud -p spacetimedb`
  (adding tables or reducers keeps the data; changing a table's columns needs a reset).
- Seed the demo items and areas: `backend\.venv\Scripts\python.exe -m backend.seed_spacetime`.
- Between demo runs: call `reset_memory`.

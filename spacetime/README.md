# spacetime

SpacetimeDB module (TypeScript) for the database `nemodb-g8356` on Maincloud.

- Tables and reducers: `docs/interfaces.md` sections 2 and 3.
- The memory logic must live in reducers, not in Python:
  - **last seen:** `add_sighting` updates `item_state` once an item is seen `CONFIRM_FRAMES` (2)
    times in a row in the same area and furniture;
  - **add_frame:** vision reports each kept frame, so a sharp frame showing an important item's
    furniture without the item marks it missing;
  - **used:** that item seen back on the same furniture in the same area.
- Publish from this folder: `spacetime publish nemodb-g8356 -s maincloud -p spacetimedb`

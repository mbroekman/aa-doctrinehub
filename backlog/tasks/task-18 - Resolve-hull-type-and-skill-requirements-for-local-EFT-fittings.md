---
id: TASK-18
title: Resolve hull type and skill requirements for local EFT fittings
status: Done
assignee: []
created_date: '2026-11-26 20:55'
updated_date: '2026-11-26 21:10'
labels:
  - bug
dependencies: []
ordinal: 13900
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Locally imported (EFT) fittings never got a ship_type_id or item type_ids, so they showed no ship icon and had no dogma skill requirements. An empty requirement list evaluated as green, so every character appeared able to fly e.g. a Hel. Resolve type names via eveuniverse or public ESI on import/update/sync, read required skills from eveuniverse dogma or ESI, treat an empty requirement list as unknown, and backfill existing fittings.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 EFT import and update resolve hull and item type IDs and compute dogma skill requirements
- [x] #2 A fitting without requirements evaluates as unknown, not green
- [x] #3 A failed lookup does not wipe existing requirements
- [x] #4 Existing fittings are backfilled by the daily task and a management command
- [x] #5 Tests, ruff and mypy pass
<!-- AC:END -->

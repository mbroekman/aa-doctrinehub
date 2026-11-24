---
id: TASK-1.3
title: EFT import and export with multibuy
status: Done
assignee: []
created_date: '2026-11-24 21:30'
updated_date: '2026-11-24 21:30'
labels: []
dependencies: []
parent_task_id: TASK-1
priority: medium
type: task
ordinal: 1300
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Parse EFT into slots, charges, offline state, drones and cargo; write EFT back; build multibuy text; import endpoint for managers.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria

<!-- AC:BEGIN -->
- [x] #1 Parser handles empty slots, charges, /offline, drone and cargo bays
- [x] #2 Round trip keeps items
- [x] #3 POST /doctrines/api/v1/fittings/import/ creates version 1
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
services/eft.py and services/fittings.py. Slot blocks are placed by position until SDE type resolution lands (TASK-1.8).
<!-- SECTION:NOTES:END -->

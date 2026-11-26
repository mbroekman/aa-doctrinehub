---
id: TASK-19
title: Place EFT bay items in drone, fighter or cargo bay by item type
status: Done
assignee: []
created_date: '2026-11-26 21:05'
updated_date: '2026-11-26 21:20'
labels:
  - bug
dependencies: []
ordinal: 14900
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
EFT bay blocks carry no label, so the parser put the first bay block in the drone bay. Fits without drones (e.g. Titans) showed their cargo as drones, and fighters never landed in the fighter bay. Classify bay items by EVE category (drone 18, fighter 87, else cargo) via eveuniverse or ESI on import, update and external scrape, and fix existing local fittings on refresh.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A cargo-only bay block is stored as Cargo
- [x] #2 Drones, fighters and cargo in one block are split by type
- [x] #3 Unknown types keep the positional guess
- [x] #4 doctrinehub_refresh_requirements --all fixes existing local fittings
- [x] #5 Tests, ruff and mypy pass
<!-- AC:END -->

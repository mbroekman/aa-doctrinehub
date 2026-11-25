---
id: TASK-10
title: >-
  Fix scraped doctrine name ('Doctrine information') and resolve ship_type_id
  accurately
status: Done
assignee: []
created_date: '2026-11-25 12:46'
updated_date: '2026-11-25 12:47'
labels: []
dependencies: []
ordinal: 6800
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Prevent generic 'Doctrine Information' card titles from overwriting the doctrine name scraped from the index, and resolve ship_type_id via EveType/render image instead of picking module icons from the fit page.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Generic headings like 'Doctrine Information' are ignored when extracting doctrine name
- [x] #2 ship_type_id is resolved via EveType (or /render image) matching ship_type_name instead of picking module icons
- [x] #3 Tests, ruff, and pytest pass
<!-- AC:END -->

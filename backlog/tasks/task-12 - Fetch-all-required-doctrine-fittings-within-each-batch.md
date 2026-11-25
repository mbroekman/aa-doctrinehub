---
id: TASK-12
title: Fetch all required doctrine fittings within each batch
status: Done
assignee: []
created_date: '2026-11-25 13:28'
updated_date: '2026-11-25 13:29'
labels: []
dependencies: []
ordinal: 8800
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Ensure scrape_remote_fittings_site fetches all missing fittings belonging to the doctrines in the current batch instead of truncating doctrine fittings at the batch limit, while still limiting standalone fittings.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 All missing fittings for doctrines in the current batch are fetched and linked immediately
- [x] #2 Standalone fittings and categories remain capped by the batch limit
- [x] #3 Tests, ruff, and pytest pass
<!-- AC:END -->

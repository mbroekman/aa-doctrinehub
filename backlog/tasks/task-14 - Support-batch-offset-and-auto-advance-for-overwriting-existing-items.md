---
id: TASK-14
title: Support batch offset and auto-advance for overwriting existing items
status: Done
assignee: []
created_date: '2026-11-25 14:00'
updated_date: '2026-11-25 14:02'
labels: []
dependencies: []
ordinal: 10800
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Add an offset parameter to remote_scrape preview/import and a 'Start at # (offset)' input in SyncSettingsView that auto-advances by limit after each import when Overwrite existing is enabled.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 scrape_remote_fittings_site and preview_remote_fittings_site support offset >= 0 and preserve earlier batches when offset > 0
- [x] #2 SyncSettingsView exposes 'Start at # (offset)' and auto-advances on import when Overwrite existing is enabled
- [x] #3 Frontend build, ruff, and pytest pass
<!-- AC:END -->

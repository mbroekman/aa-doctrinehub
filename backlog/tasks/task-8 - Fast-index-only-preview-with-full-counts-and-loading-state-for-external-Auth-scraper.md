---
id: TASK-8
title: >-
  Fast index-only preview with full counts and loading state for external Auth
  scraper
status: Done
assignee: []
created_date: '2026-11-25 12:18'
updated_date: '2026-11-25 12:20'
labels: []
dependencies: []
ordinal: 4800
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Make remote-scrape preview fetch only the 3 index pages (/fittings/, /fittings/fit/all/, /fittings/cat/all/) so counts (total on source, already imported, new, batch size) appear immediately, and add loading/error handling in SyncSettingsView and api.ts.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Preview mode fetches only index pages and returns total/existing/new/batch counts for doctrines, fittings, and categories
- [x] #2 SyncSettingsView shows loading indicator and detailed counts card for preview
- [x] #3 api.ts surfaces non-JSON HTTP responses instead of silently returning {}
- [x] #4 Tests, ruff, and frontend build pass
<!-- AC:END -->

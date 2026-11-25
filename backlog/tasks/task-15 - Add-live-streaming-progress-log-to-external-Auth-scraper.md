---
id: TASK-15
title: Add live streaming progress log to external Auth scraper
status: Done
assignee: []
created_date: '2026-11-25 14:29'
updated_date: '2026-11-25 14:31'
labels: []
dependencies: []
ordinal: 11800
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Stream step-by-step progress log lines as NDJSON from remote_scrape when stream=true (with X-Accel-Buffering: no) and render a live scrolling log panel alongside the preview/import summary in SyncSettingsView.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 scrape_remote_fittings_site and preview_remote_fittings_site emit progress log lines via on_progress callback
- [x] #2 remote_scrape view supports stream=true returning application/x-ndjson with X-Accel-Buffering: no
- [x] #3 SyncSettingsView displays a live progress log alongside Preview and Import summary
- [x] #4 Frontend build, ruff, and pytest pass
<!-- AC:END -->

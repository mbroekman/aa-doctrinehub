---
id: TASK-9
title: Show detailed import summary card after external Auth scrape
status: Done
assignee: []
created_date: '2026-11-25 12:42'
updated_date: '2026-11-25 12:43'
labels: []
dependencies: []
ordinal: 5800
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Return imported doctrine names and total stored External Auth counts from remote_scrape import mode and render a structured Import Summary card in SyncSettingsView.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 remote_scrape import response includes summary, stored totals, and imported doctrine list
- [x] #2 SyncSettingsView renders a structured Import Summary card after import
- [x] #3 Tests, ruff, and frontend build pass
<!-- AC:END -->

---
id: TASK-11
title: Add purge imported External Auth items and Overwrite existing option
status: Done
assignee: []
created_date: '2026-11-25 12:51'
updated_date: '2026-11-25 12:53'
labels: []
dependencies: []
ordinal: 7800
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Add a purge endpoint and in-page confirmation UI to delete all Source.REMOTE_AUTH doctrines, fittings, and categories, and expose an explicit 'Overwrite existing' option in SyncSettingsView.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 POST /api/v1/settings/remote-scrape/purge/ removes Source.REMOTE_AUTH records while preserving Source.LOCAL records
- [x] #2 SyncSettingsView exposes 'Overwrite existing' toggle and 'Delete imported items' with in-page confirmation
- [x] #3 Tests, ruff, and frontend build pass
<!-- AC:END -->

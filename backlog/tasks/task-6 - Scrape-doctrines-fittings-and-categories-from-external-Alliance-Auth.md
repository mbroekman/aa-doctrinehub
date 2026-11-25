---
id: TASK-6
title: 'Scrape doctrines, fittings, and categories from external Alliance Auth'
status: Done
assignee: []
created_date: '2026-11-25 11:04'
updated_date: '2026-11-25 11:09'
labels: []
dependencies: []
ordinal: 2800
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Add read-only Source.REMOTE_AUTH scraping of doctrines, fittings, and categories from an external Alliance Auth Fittings instance using a one-time sessionid cookie, reusing SourceSnapshot/apply_snapshot and exposing a preview + import flow in SyncSettingsView.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Source.REMOTE_AUTH added to models.Source with migration and read-only protection
- [x] #2 remote_scrape.py scrapes doctrines, fittings (EFT + notes), and categories from external Auth via sessionid cookie without storing the cookie
- [x] #3 SPA Settings view allows preview (dry-run) and import of external Auth doctrines, fittings, and categories
- [x] #4 Unit tests, ruff, mypy, and frontend build pass
<!-- AC:END -->

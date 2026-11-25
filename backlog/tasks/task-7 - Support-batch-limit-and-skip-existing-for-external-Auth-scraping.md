---
id: TASK-7
title: Support batch limit and skip-existing for external Auth scraping
status: Done
assignee: []
created_date: '2026-11-25 12:12'
updated_date: '2026-11-25 12:14'
labels: []
dependencies: []
ordinal: 3800
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Allow specifying a batch limit and skipping already-imported Source.REMOTE_AUTH items when scraping an external Alliance Auth instance, preserving previously imported records when running partial batches.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 scrape_remote_fittings_site supports limit and skip_existing without pruning existing records on partial batches
- [x] #2 API and SyncSettingsView expose batch limit and skip_existing options with total-available counts in preview
- [x] #3 Tests verify batched import preserves earlier batches and ruff + pytest + frontend build pass
<!-- AC:END -->

---
id: TASK-1.4
title: Periodic read-only sync from the Fittings app
status: Done
assignee: []
created_date: '2026-11-24 21:30'
updated_date: '2026-11-24 21:30'
labels: []
dependencies: []
parent_task_id: TASK-1
priority: medium
type: task
ordinal: 1400
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner decision 2026-11-24: copy doctrines, fittings and categories from Fittings on the same Auth on a configurable interval (default 7 days), labelled and read-only. Approved exception to workspace AGENTS section 15: read via app registry only, never import fittings.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria

<!-- AC:BEGIN -->
- [x] #1 Sync creates and updates fittings with a new version only on change
- [x] #2 Removed doctrines are archived; removed fittings deleted unless used by a local doctrine
- [x] #3 Category group restrictions copied
- [x] #4 Settings and Sync now in the frontend
- [x] #5 Daily beat task aa_doctrinehub.tasks.sync_from_fittings honours interval
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Reader maps Fittings v2.3.3 fields (Fitting.ship_type_type_id, FittingItem.flag/type_id/quantity, Doctrine.fittings, Category.groups) to dataclasses; apply_snapshot is tested without Fittings installed.
<!-- SECTION:NOTES:END -->

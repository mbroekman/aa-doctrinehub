---
id: TASK-1.2
title: Catalogue data model with sources and versions
status: Done
assignee: []
created_date: '2026-11-24 21:30'
updated_date: '2026-11-24 21:30'
labels: []
dependencies: []
parent_task_id: TASK-1
priority: medium
type: task
ordinal: 1200
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Models for Category, Doctrine (status), Fitting, immutable FittingVersion, FittingItem and DoctrineFitting (role, required, target count). Every sourced record has source and external_id; non-local records are read-only.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria

<!-- AC:BEGIN -->
- [x] #1 Models and initial migration
- [x] #2 Unique (source, external_id) for synced records
- [x] #3 is_editable is false for non-local records
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Migration 0001_initial. SyncSettings singleton holds functional sync settings.
<!-- SECTION:NOTES:END -->

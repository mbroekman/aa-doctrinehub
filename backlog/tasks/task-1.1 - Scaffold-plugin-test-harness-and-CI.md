---
id: TASK-1.1
title: Scaffold plugin, test harness and CI
status: Done
assignee: []
created_date: '2026-11-24 21:30'
updated_date: '2026-11-24 21:30'
labels: []
dependencies: []
parent_task_id: TASK-1
priority: medium
type: task
ordinal: 1100
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Create the aa_doctrinehub Django app following aa-kanban conventions: hatchling + uv, Ruff (120), mypy with django-stubs, pytest-django with testauth, pre-commit and GitHub Actions, app permissions.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria

<!-- AC:BEGIN -->
- [x] #1 App installs in testauth and migrations run
- [x] #2 Permissions basic_access, manage_doctrines, view_compliance, manage_rules exist
- [x] #3 pytest, ruff and mypy pass
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Copied testauth, tox, pytest, Makefile, pre-commit and CI from aa-kanban and renamed. Permissions on unmanaged General model.
<!-- SECTION:NOTES:END -->

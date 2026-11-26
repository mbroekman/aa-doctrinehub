---
id: TASK-17
title: Fix unreadable select and textarea text in dark theme
status: Done
assignee: []
created_date: '2026-11-26 19:55'
updated_date: '2026-11-26 20:05'
labels:
  - ui
  - bug
dependencies: []
ordinal: 12900
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
In the dark theme the native `<select>` dropdowns (rule editor, filters, Hangars & SRP) showed dark grey text on a dark background. Native selects and textareas do not inherit the text colour; the browser and Alliance Auth's Bootstrap theme set their own. Pin native form controls to the SPA theme variables and set `color-scheme` per theme so native popups follow it too.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Native select, option and textarea text uses the theme foreground colour in dark and light theme
- [x] #2 `color-scheme` follows the active theme so native dropdown popups and checkboxes render correctly
- [x] #3 Frontend build passes and the bundled assets are updated
<!-- AC:END -->

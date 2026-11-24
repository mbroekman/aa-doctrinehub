---
id: TASK-3
title: Phase 3: Compliance rules and automatic Auth groups
status: To Do
assignee: []
created_date: '2026-11-24 21:30'
updated_date: '2026-11-24 21:30'
labels: []
dependencies:
  - TASK-2
priority: medium
type: task
ordinal: 3000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Rules in the management part of the SPA link a tree of conditions (can fly fitting, doctrine coverage, skill, total SP, ship owned, implants, membership, other group) to an Auth group. All characters of the account are evaluated.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria

<!-- AC:BEGIN -->
- [ ] #1 Rule builder with AND, OR and at-least-N
- [ ] #2 Modes: report only (default for new rules), automatic, reviewer approval
- [ ] #3 Revocation only after DM warning and grace period; ESI errors set status unknown and never revoke
- [ ] #4 Only grants made by the plugin are revoked (GroupGrant)
- [ ] #5 Audit log of every grant and revocation
- [ ] #6 Discord messages via discord_i18n in a fixed language
- [ ] #7 First rule: SIG: Capitals
<!-- AC:END -->

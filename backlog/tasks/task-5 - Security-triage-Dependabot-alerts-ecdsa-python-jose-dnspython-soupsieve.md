---
id: TASK-5
title: Security triage Dependabot alerts (ecdsa, python-jose, dnspython, soupsieve)
status: Done
assignee: []
created_date: '2026-11-25 07:30'
updated_date: '2026-11-25 07:30'
labels: []
dependencies: []
ordinal: 1000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
7 Dependabot alerts opened on the initial scaffold PR, all transitive
dependencies via `allianceauth`/`django-esi` - nothing aa-doctrinehub
imports directly.
<!-- SECTION:DESCRIPTION:END -->

## Findings & Actions

<!-- SECTION:NOTES:BEGIN -->
- **ecdsa (#1), python-jose (#2):** no patched release exists upstream at
  all (ecdsa's Minerva timing attack is a declared "won't fix" by the
  maintainer; python-jose's CVE-2026-85394 fix is incomplete, 3.5.0 is
  latest and still affected). Dismissed as `tolerable_risk`, matching the
  identical dismissal already recorded on aa-kanban TASK-86.
- **dnspython (#3, #7), soupsieve (#4, #5, #6):** a real fix exists
  (dnspython >= 2.9.0, soupsieve >= 3.0.2/4.0.0), but those releases
  require Python >= 3.11 / >= 3.11.5 respectively. This project's tox
  `env_list` still supports Python 3.10 (and soupsieve's floor also
  blocks early 3.11.0-3.11.4), so `uv.lock`'s resolver has no choice but
  the vulnerable version for those interpreters.
  - Upgraded `uv.lock` so Python >= 3.11.5 already gets the patched
    soupsieve 4.1.3 (dnspython was already correctly split by Python
    version - 2.9.2 for >= 3.11, 2.8.0 only for < 3.11).
  - Dismissed the remaining alerts as `tolerable_risk` with a note that
    they resolve automatically once Python 3.10 support is dropped.
  - **Follow-up (not done here, a policy decision):** dropping Python
    3.10 from `tox.ini`/`pyproject.toml`/CI matrix would let `uv lock`
    pick up the fully patched versions everywhere and let these 2
    alerts close on their own. Flagged to the user; not actioned since
    it means ending support for a Python version, not a pure dependency
    bump.
<!-- SECTION:NOTES:END -->

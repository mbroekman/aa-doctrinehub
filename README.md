# AA Doctrine Hub

Doctrines, fittings and member compliance for [Alliance Auth](https://gitlab.com/allianceauth/allianceauth).
A modern successor to the community Fittings app.

> **Status:** early development (phase 1, catalogue). See `backlog/docs/doc-1` for the design.

## Features

Phase 1 (in progress):

- Doctrines with fittings, roles (DPS, logistics, tackle, ...), required or optional, and a target count.
- Fittings with versions: every change is a new version with author, time and note.
- EFT import and export, multibuy text for one or more fits.
- Categories that limit visibility to Auth groups.
- Periodic sync from the Fittings app on the same Auth (optional). Synced doctrines and fittings
  carry the source label "Fittings" and are read-only here.
- React + Tailwind + shadcn/ui single-page app that follows the Alliance Auth light/dark theme.

Planned: per-character eligibility from ESI skills, skill plans, coverage reports for leadership,
and compliance rules that assign and revoke Auth groups automatically.

## Installation

1. Install the package in your Auth virtual environment:

   ```bash
   pip install aa-doctrinehub
   ```

2. Add `"aa_doctrinehub"` to `INSTALLED_APPS` in `local.py`.

3. Add the periodic task to `local.py`:

   ```python
   CELERYBEAT_SCHEDULE["aa_doctrinehub_sync_from_fittings"] = {
       "task": "aa_doctrinehub.tasks.sync_from_fittings",
       "schedule": crontab(minute="30", hour="4"),
   }
   ```

4. Run migrations and collect static files, then restart Auth and the Celery workers:

   ```bash
   python manage.py migrate
   python manage.py collectstatic --noinput
   ```

## Periodic tasks (CELERYBEAT_SCHEDULE)

| Name | Task | Schedule | What it does |
| --- | --- | --- | --- |
| `aa_doctrinehub_sync_from_fittings` | `aa_doctrinehub.tasks.sync_from_fittings` | daily, 04:30 | Copies doctrines, fittings and categories from the Fittings app when the sync is enabled and its interval (set in the app, default 7 days) has passed. Does nothing when Fittings is not installed. |

## Permissions

| Permission | For |
| --- | --- |
| `aa_doctrinehub.basic_access` | Members: see doctrines and fittings |
| `aa_doctrinehub.manage_doctrines` | Doctrine managers: import and edit fittings, sync settings |
| `aa_doctrinehub.view_compliance` | FCs and leadership: coverage and member status (planned) |
| `aa_doctrinehub.manage_rules` | Compliance rules and group assignments (planned) |

## Settings

| Setting | Default | Description |
| --- | --- | --- |
| `DOCTRINEHUB_APP_NAME` | `"Doctrines"` | Name in the menu and page title |

Functional settings (Fittings sync on/off and interval) live in the app itself, not in Django admin.

## Fittings sync

Doctrine Hub never imports the Fittings package. It looks up Fittings' models through Django's app
registry, so it works with or without Fittings installed. Sync behaviour:

- Fittings and doctrines are matched on their Fittings ID; a changed fitting gets a new version.
- Doctrines removed from Fittings are archived here; fittings removed from Fittings are deleted,
  unless one of our own doctrines still uses them.
- Category group restrictions are copied.

## Development

```bash
uv sync
uv run pytest
uv run ruff check . && uv run ruff format --check .
uv run mypy aa_doctrinehub
```

Frontend (React 19 + Vite + Tailwind v4 + shadcn/ui), output goes to `aa_doctrinehub/static/aa_doctrinehub/spa/`:

```bash
cd frontend && npm install && npm run build
```

On Windows with the workspace on Google Drive, use `frontend/build.ps1` (builds on a local disk).

# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Removed

- **Python 3.10 support dropped.** Minimum supported version is now Python 3.11.

### Fixed

- **External Auth scraper (TASK-10, TASK-12):** Ignored generic `"Doctrine Information"` card headings so the real doctrine name from the index is preserved, restricted doctrine icon extraction to `images.evetech.net/types/` (never character portraits), resolved `ship_type_id` via `EveType` (matching `ship_type_name`) or `/render` ship images instead of picking module icons from the fitting page, and ensured batched scrapes always fetch all missing fittings required by the doctrines in the current batch.

### Added

- **Search & filters (TASK-13):** Enhanced the SPA search bar in `App.tsx` to search across doctrine names, descriptions, categories, roles, ship types, and fitting names, added category and source dropdown filters with reset/clear controls, and added item counts to the **Doctrines** and **Fittings** tabs.
- **External Auth scraper (TASK-6 t/m TASK-11, TASK-14, TASK-15):** Added `Source.REMOTE_AUTH` (`External Auth`, read-only), `remote_scrape.py`, `POST /api/v1/settings/remote-scrape/` (with `stream=true` NDJSON live progress), `POST /api/v1/settings/remote-scrape/purge/`, and the **Import from External Auth** preview/import card in Settings to scrape doctrines, fittings, and categories from another Alliance Auth instance using a one-time `sessionid` cookie, including batch `limit`, `offset` (auto-advancing when overwriting), `Overwrite existing` toggle, fast index-only preview with full totals, a structured **Import summary** card, **Delete imported items** with in-page confirmation, and a live scrolling progress log.
- **Dutch translation:** `locale/nl` for model names, statuses and roles.

- **Project scaffolding (TASK-1.1):** Django app `aa_doctrinehub` with permissions (`basic_access`,
  `manage_doctrines`, `view_compliance`, `manage_rules`), test harness, CI and pre-commit configuration.
- **Catalogue models (TASK-1.2):** categories with group visibility, doctrines with status, fittings with
  immutable versions and items, doctrine roles, required/optional and target counts. Every record has a
  `source` (Doctrine Hub or Fittings).
- **EFT import and export (TASK-1.3):** EFT parser and writer, multibuy text, import endpoint.
- **Fittings sync (TASK-1.4):** periodic, optional copy of doctrines, fittings and categories from the
  Fittings app on the same Auth, read-only and labelled "Fittings". New periodic task
  `aa_doctrinehub.tasks.sync_from_fittings`.
- **SPA foundation (TASK-1.5):** React 19 + Vite + Tailwind v4 + shadcn/ui app with doctrine overview,
  fitting detail (copy EFT and multibuy) and sync settings.

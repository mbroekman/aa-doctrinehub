# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Removed

- **Python 3.10 support dropped.** Minimum supported version is now Python 3.11.

### Fixed

- **Cargo shown as drones (TASK-19):** EFT bay items are now placed in the drone bay, fighter bay or cargo by their item type (via `eveuniverse` or ESI) instead of by block position, so fits without drones (e.g. Titans) no longer show their cargo as drones. Existing own fittings are fixed with `python manage.py doctrinehub_refresh_requirements --all`.
- **Own (EFT) fittings without icon and skill check (TASK-18):** Imported and edited fittings now resolve the hull and item type IDs (via `eveuniverse` or public ESI `/universe/ids/`) and get their dogma skill requirements (via `eveuniverse` dogma or ESI `/universe/types/{id}/`). A fitting without any skill requirements now shows `unknown` instead of green for everyone. Existing fittings are backfilled by the daily `sync_from_fittings` task, or immediately with `python manage.py doctrinehub_refresh_requirements`.
- **Dark theme form controls (TASK-17):** Dropdowns (`<select>`) and the SRP killmail textarea now use the theme text colour instead of the browser/Bootstrap default, which was dark grey on a dark background. `color-scheme` now follows the active theme so native dropdown lists and checkboxes match.
- **External Auth scraper (TASK-10, TASK-12):** Ignored generic `"Doctrine Information"` card headings so the real doctrine name from the index is preserved, restricted doctrine icon extraction to `images.evetech.net/types/` (never character portraits), resolved `ship_type_id` via `EveType` (matching `ship_type_name`) or `/render` ship images instead of picking module icons from the fitting page, and ensured batched scrapes always fetch all missing fittings required by the doctrines in the current batch.

### Added

- **Phase 4 — Integrations (TASK-4):** Hangar check for fitted doctrine ships per character/location (`GET /api/v1/integrations/hangar-check/`), `aa-fatanalysis` fleet participation rule condition, pushing doctrine ship shortages to `aa-industry` (`POST /api/v1/integrations/industry-order/`), and SRP killmail vs. doctrine fit comparison (`POST /api/v1/integrations/srp-compare/`), with a **Hangars & SRP** SPA tab.
- **Phase 3 — Compliance Rules & Automatic Auth Groups (TASK-3):** Recursive `AND`/`OR`/`AT_LEAST` rule builder (`ComplianceRule`, `RuleEvaluation`, `GroupGrant`, `PendingApproval`, `ComplianceAuditLog`) with `report_only` (default), `automatic`, and `reviewer_approval` modes, DM warnings + grace period before revocation, `unknown` safety on ESI errors, fixed-language Discord notifications (`discord_i18n.py`, `NotificationConfig`), initial `SIG: Capitals` rule, Celery task `evaluate_compliance_rules`, and **Rules & Groups** SPA tab.
- **Phase 2 — Eligibility & ESI Skills (TASK-2):** Mandatory ESI character linking (`/doctrines/link-character/`), 4-hourly own ESI sync (`CharacterSkillSnapshot`, `CharacterSkill`, `CharacterImplant`, `CharacterAsset`, `sync_character_snapshots`), dogma + manual skill requirements (`FittingSkillRequirement`), per-character/account traffic lights, EVE skill plan export, doctrine/role coverage overview, skill gap analysis, and **Compliance** SPA tab.
- **Search & filters (TASK-13):** Enhanced the SPA search bar in `App.tsx` to search across doctrine names, descriptions, categories, roles, ship types, and fitting names, added category and source dropdown filters with reset/clear controls, and added item counts to the **Doctrines** and **Fittings** tabs.
- **External Auth scraper (TASK-6 t/m TASK-11, TASK-14 t/m TASK-16):** Added `Source.REMOTE_AUTH` (`External Auth`, read-only), `remote_scrape.py`, `POST /api/v1/settings/remote-scrape/` (with `stream=true` NDJSON live progress), `POST /api/v1/settings/remote-scrape/purge/`, and the **Import from External Auth** preview/import card in Settings to scrape doctrines, fittings, and categories from another Alliance Auth instance using a one-time `sessionid` cookie, including batch `limit`, `offset` (auto-advancing when overwriting), `Overwrite existing` toggle, fast index-only preview with full totals, a structured **Import summary** card, **Delete imported items** with in-page confirmation, and a live progress log (newest entry on top).
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

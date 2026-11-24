# AA-DoctrineHub - AI Agent Guidelines

Dit project maakt onderdeel uit van de Workbench 001 workspace en erft alle bindende richtlijnen van het centrale hoofd-instructiedocument:
👉 **[Centrale AGENTS.md](file:///g:/My%20Drive/Workbench%20001/AGENTS.md)**

Lees tevens altijd eerst [.agent/memory.md](file:///g:/My%20Drive/Workbench%20001/.agent/memory.md) vóór analyse of modificatie (Regel 1 van AGENTS.md).

______________________________________________________________________

## 1. Project Context & Backlog Directory

- **Plugin:** `aa-doctrinehub` (Django App: `aa_doctrinehub`, URL-prefix `/doctrines/`)
- **Doel:** moderne opvolger van de community-app Fittings: doctrines en fits overzichtelijk per lid, geschiktheid per karakter uit ESI, en regels die Auth-groepen automatisch toekennen en intrekken.
- **Ontwerp:** `backlog/docs/doc-1 - Design-Doctrine-Hub.md`.
- **Backlog Map:** `plugins/aa-doctrinehub/backlog/`. Voer `backlog` commando's uit vanuit deze map. Taken in het Engels.

______________________________________________________________________

## 2. Project-Specifieke Conventies

### Bronnen en alleen-lezen records

- `Category`, `Doctrine` en `Fitting` hebben een `source` (`local` of `fittings`) en een `external_id`.
- Records met een andere bron dan `local` zijn alleen-lezen in Doctrine Hub (`is_editable`). Wijzigingen lopen via de sync, nooit via de UI.
- De frontend toont zulke records altijd met een bronlabel (`SourceBadge`).

### Fittings-sync: goedgekeurde uitzondering op centrale AGENTS §15

- Besluit van de eigenaar (2026-11-24): fits en doctrines uit de Fittings-app op dezelfde Auth periodiek (instelbaar, standaard 7 dagen) overnemen.
- Alleen `services/fittings_sync.py` leest Fittings, via `django.apps.apps.get_model("fittings", ...)`. **Nooit** `import fittings`; `test_no_external_plugins.py` bewaakt dat.
- De reader zet rijen om naar dataclasses (`SourceSnapshot`); `apply_snapshot` werkt alleen op die dataclasses en is los te testen.
- Verdwenen doctrines worden gearchiveerd, verdwenen fits verwijderd tenzij een eigen doctrine ze gebruikt.

### Fitting-versies

- Een `FittingVersion` is onveranderlijk. Een wijziging is altijd een nieuwe versie (`services/fittings.add_version`).
- EFT is de uitwisselvorm; `services/eft.py` parseert en schrijft EFT zonder SDE (slots op positie). Type-resolutie via `django-eveuniverse` volgt in fase 2.

### Compliance (fase 2 en 3)

- Skills, assets en clones haalt de plugin zelf op via ESI (`django-esi`), opgeslagen in eigen modellen. Geen `memberaudit` of `corptools`.
- ESI-koppeling van karakters is verplicht; regels kijken naar alle karakters van een account.
- Regels zijn onderdeel van het beheerdeel in de frontend (niet `/admin/`), starten in rapportmodus, en trekken een groep pas in na een DM-waarschuwing en respijtperiode. Een ESI-fout of verlopen token trekt nooit iets in.

### Frontend

- React 19 + TypeScript + Vite + Tailwind v4 (zonder Preflight, gescoped onder `.aa-spa-root`) + shadcn/ui, zoals aa-kanban v2.
- Build naar `aa_doctrinehub/static/aa_doctrinehub/spa/assets/` (gecommit). Op Google Drive: `frontend/build.ps1`.

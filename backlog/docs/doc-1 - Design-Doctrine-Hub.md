---
id: doc-1
title: Design Doctrine Hub
type: specification
created_date: '2026-11-24 21:30'
updated_date: '2026-11-24 21:30'
---

# Ontwerp: Doctrine Hub (aa-doctrinehub)

Volledig voorstel (met diagram en motivatie): [Ontwerpvoorstel: moderne Fittings & Doctrine plugin](https://claude.ai/artifact/LNvGKVaS6z7syuZC2w8NKL). Dit document legt de besluiten vast.

## Doel

Een eigen opvolger van Fittings (colcrunch, v2.3.3) die drie dingen doet:

1. Doctrines en fits overzichtelijk tonen per lid.
2. Per karakter laten zien welke fits het kan vliegen en wat er mist.
3. Op basis van regels automatisch Auth-groepen toekennen en intrekken.

## Besluiten (2026-11-24, eigenaar)

| Vraag | Besluit |
| --- | --- |
| Naam | `aa-doctrinehub`, app `aa_doctrinehub`, repo `mbroekman/aa-doctrinehub` |
| Karakters bij regels | Alle karakters van het account tellen mee |
| Plek van regels | Beheerdeel van de plugin in de frontend, niet `/admin/` |
| Koppeling | ESI-koppeling van karakters is altijd verplicht |
| Bestaande Fittings | Periodieke sync (instelbaar, standaard 7 dagen) uit de Fittings-app op dezelfde Auth. Gesynchroniseerde items hebben bronlabel "Fittings" en zijn alleen-lezen. |

De Fittings-sync is een bewuste uitzondering op AGENTS §15: alleen `services/fittings_sync.py` leest Fittings, via het Django app-register, nooit via `import fittings`.

## Fasering

| Fase | Inhoud | Taak |
| --- | --- | --- |
| 1 | Catalogus: doctrines, fits met versies, EFT, multibuy, Save to EVE, categorieën, Fittings-sync, SPA | TASK-1 |
| 2 | Geschiktheid per karakter uit eigen ESI-sync, skillplannen, dekkingsoverzicht | TASK-2 |
| 3 | Regels en automatische groepen: rapportmodus, respijt, audit log, Discord | TASK-3 |
| 4 | Koppelingen: hangar-check, aa-fatanalysis, aa-industry, SRP | TASK-4 |

## Uitgangspunten compliance

- Nieuwe regels starten in rapportmodus.
- Intrekken alleen na DM-waarschuwing en respijtperiode.
- Een ESI-fout of verlopen token zet de status op "onbekend" en trekt nooit iets in.
- De plugin trekt alleen groepen in die ze zelf heeft toegekend.

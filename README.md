# SmartCamper Suite

**Phase 2D development — not a production release.**

<p align="center"><img src="docs/assets/smartcamper-suite-logo-set.png" alt="SmartCamper Suite Logo-Set" width="720"></p>

SmartCamper Suite – Eine modulare Home-Assistant-Integration für
Wohnmobilreisen, Tankstellen, Routenplanung und Grenzwartezeiten.

SmartCamper Suite is a single modular Home Assistant custom integration under
the domain `smartcamper_suite`. It provides one shared vehicle registry,
provider/account boundary, credential abstraction, offline API infrastructure,
versioned suite storage, four isolated module runtimes, and the foundation for
`custom:smartcamper-card`.

## Current scope

The `fuel_stations` module now provides offline-testable Tankerkönig, Petromap
and Nakordoni adapters, vehicle-scoped search settings, shared provider
credentials, provider fallback, per-vehicle sensors and the fuel-stations view
in `custom:smartcamper-card`. The card includes multi-fuel prices, sorting,
highlights, navigation, provider logos, diagnostics, automatic/movement-based
refresh and manual refresh. OAuth refresh and legacy migration are tested as
isolated candidate paths; no legacy entry is changed automatically.

This is still development code. It does not open or migrate a productive
database, use real credentials, perform live API calls in tests, or install
anything in Home Assistant VM 104.

Das `route_planner`-Modul verwendet die zentralen Fahrzeugprofile und bietet
explizite Routenberechnung, interaktive Start-/Ziel-/Zwischenstoppbearbeitung,
sichtbare Beta-/Restriktions- und Mautwarnungen sowie GPX Route/Track/Combined-
Downloads. Nakordoni-Motorhome-Routing wird nicht als rechtlich validierte
Navigation dargestellt; automatische Hintergrundberechnung ist absichtlich
deaktiviert. Details stehen in
[docs/phase-2c-route-planner-plan.md](docs/phase-2c-route-planner-plan.md).

Das `travel_journal`-Modul verwendet ebenfalls ausschließlich die zentralen
Fahrzeugprofile. Es bietet die grundlegenden Reise-, Aufenthalts-,
Zwischenstopp- und Kostenoperationen, fahrzeugbezogene Journal-Sensoren und
eine getrennte, versionierte SQLite-Datei. Ein Legacy-Import ist nur als
expliziter Opt-in-Dry-Run beziehungsweise Import mit SHA-256-Idempotenz
möglich; die alte Datenbank wird read-only geöffnet und nie automatisch
verändert. Die vollständige Stable-Matrix und die bewusst noch offenen
Adapter sind in [docs/phase-2d-travel-journal-plan.md](docs/phase-2d-travel-journal-plan.md)
beschrieben.

## Module

| Modul | Darstellung | Status |
|---|---|---|
| Camper Travel Journal | [Reisetagebuch](docs/assets/module-travel-journal.svg) | Phase-2D-Grundfunktionen, offline getestet |
| Mobile Fuel Stations | [Tankstellen](docs/assets/module-fuel-stations.svg) | Phase-2B-Kandidat, offline getestet |
| Camper Route Planner | [Routenplanung](docs/assets/module-route-planner.svg) | Phase-2C-Kandidat, offline getestet |
| Wartezeiten Forecast | [Grenzwartezeiten](docs/assets/module-border-forecast.svg) | Platzhalter, Phase 2B nicht implementiert |

Die Branding-Pfade und die Herkunft der freigegebenen Logo-Datei sind in
[docs/branding.md](docs/branding.md) dokumentiert.

## Development

```bash
python -m pytest
python -m compileall custom_components tests
ruff check .
cd frontend && npm ci && npm test && npm run build
npm run browser:test
```

See [README.en.md](README.en.md), [docs/architecture.md](docs/architecture.md)
and [docs/development.md](docs/development.md).
The implementation plan and deviations are in
[docs/phase-2b-mobile-fuel-stations-plan.md](docs/phase-2b-mobile-fuel-stations-plan.md).
The detailed v0.8.4 comparison is in
[docs/phase-2b-feature-matrix.md](docs/phase-2b-feature-matrix.md).
The QA status and remaining merge gates are in
[docs/phase-2a-qa.md](docs/phase-2a-qa.md).
The Travel Journal Stable inventory, isolated database design and opt-in
legacy import boundary are in
[docs/phase-2d-travel-journal-plan.md](docs/phase-2d-travel-journal-plan.md).

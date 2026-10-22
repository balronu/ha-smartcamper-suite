# SmartCamper Suite

[Deutsch](README.md) | [English](README.en.md)

**Öffentliche Test-Beta: `v0.3.0-beta.3` (Hotfix-Kandidat).**

Die Stable-Integrationen bleiben die Produktionsreferenz. Diese Beta ist nur
für einen isolierten, kontrollierten Home-Assistant-Test vorgesehen.

<p align="center"><img src="docs/assets/smartcamper-suite-logo-set.png" alt="SmartCamper Suite Logo-Set" width="720"></p>

SmartCamper Suite – Eine modulare Home-Assistant-Integration für
Wohnmobilreisen, Tankstellen, Routenplanung und Grenzwartezeiten.

SmartCamper Suite ist eine modulare Home-Assistant-Custom-Integration unter
der Domain `smartcamper_suite`. Sie bietet eine zentrale Fahrzeugverwaltung,
gemeinsame Provider- und Credential-Grenzen, offline testbare API-Pfade,
versionierten Suite-Speicher, vier getrennte Modul-Laufzeiten und die zentrale
Karte `custom:smartcamper-card`.

## Aktueller Entwicklungsstand

### HACS-Testinstallation

Die Beta kann über **HACS → Integrationen → Benutzerdefinierte Repositories**
installiert werden. Repository hinzufügen:
`https://github.com/balronu/ha-smartcamper-suite`, Typ **Integration**.
Danach die Pre-Release-Auswahl aktivieren und `v0.3.0-beta.3` installieren,
sobald der Release veröffentlicht ist.
Nach der Installation Home Assistant neu starten und die Suite unter
**Einstellungen → Geräte & Dienste** als separaten Config Entry hinzufügen.
Bestehende Stable-Integrationen werden nicht ersetzt oder entfernt.

Für den ersten Test nur synthetische beziehungsweise ausdrücklich freigegebene
Providerdaten verwenden. Ein echter Legacy-Journal-Import ist nicht Teil der
Installation; zunächst ist ausschließlich der Dry-Run zulässig.

Das Modul `fuel_stations` bietet offline testbare Tankerkönig-, Petromap- und
Nakordoni-Adapter, fahrzeugbezogene Suchparameter, gemeinsame Provider-
Zugangsdaten, Fallback, Sensoren je Fahrzeug und die Tankstellenansicht in
`custom:smartcamper-card`. Die Karte unterstützt mehrere Kraftstoffe,
Sortierung, Hervorhebungen, Navigation, Anbieterlogos, Diagnostik,
automatische/bewegungsabhängige Aktualisierung und manuelle Aktualisierung.
OAuth-Aktualisierung und Legacy-Migration sind isoliert getestet; kein Legacy-
Entry wird automatisch verändert.

Dies ist eine kontrollierte Test-Beta und keine Stable-Version. Die Suite
öffnet oder migriert keine produktive Datenbank, verwendet in Tests keine
echten Zugangsdaten, führt in Tests keine Live-API-Aufrufe aus und wird nicht
auf Home-Assistant-VM 104 installiert. Die drei Stable-Integrationen bleiben
parallel installiert.

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

Die Vorbereitung des ersten isolierten HA-Praxistests steht in
[docs/phase-2d-home-assistant-practical-test.md](docs/phase-2d-home-assistant-practical-test.md).

## Module

| Modul | Darstellung | Status |
|---|---|---|
| Camper Travel Journal | [Reisetagebuch](docs/assets/module-travel-journal.svg) | Phase-2D-Grundfunktionen, offline getestet |
| Mobile Fuel Stations | [Tankstellen](docs/assets/module-fuel-stations.svg) | Phase-2B-Kandidat, offline getestet |
| Camper Route Planner | [Routenplanung](docs/assets/module-route-planner.svg) | Phase-2C-Kandidat, offline getestet |

Die Branding-Pfade und die Herkunft der freigegebenen Logo-Datei sind in
[docs/branding.md](docs/branding.md) dokumentiert.

## Bilder und Screenshot-Nachweise

Das Logo und die Modul-Illustrationen liegen dauerhaft unter `docs/assets/`.
Die folgenden UI-Bilder stammen aus dem isolierten Chromium-Fixture mit
synthetischen Home-Assistant-Daten:

| Ansicht | Bild |
|---|---|
| Mobile Fuel Stations | ![Mobile Fuel Stations](docs/images/smartcamper-card-fuel-stations.png) |
| Camper Route Planner | ![Camper Route Planner](docs/images/smartcamper-card-route-planner.png) |
| Camper Travel Journal | ![Camper Travel Journal](docs/images/smartcamper-card-travel-journal.png) |
| Karten-Konfiguration | ![Karten-Konfiguration](docs/images/smartcamper-card-configuration.png) |

Die zentrale Fahrzeugverwaltung läuft über den Home-Assistant-Config- und
Options-Flow. Für diese HA-Oberfläche existiert im Repository noch kein
vollständiger Chromium-Fixture; deshalb wird dafür kein Screenshot erfunden.
Der Pfad ist durch die HA-Fixture- und Config-Flow-Tests abgedeckt.

## Entwicklung

```bash
python -m pytest
python -m compileall custom_components tests
ruff check .
cd frontend && npm ci && npm test && npm run build
npm run browser:test
```

Siehe [README.en.md](README.en.md), [docs/architecture.md](docs/architecture.md)
und [docs/development.md](docs/development.md).
Der Implementierungsplan und die Abweichungen stehen in
[docs/phase-2b-mobile-fuel-stations-plan.md](docs/phase-2b-mobile-fuel-stations-plan.md).
Der detaillierte Vergleich mit v0.8.4 steht in
[docs/phase-2b-feature-matrix.md](docs/phase-2b-feature-matrix.md).
Der QA-Status und die abgeschlossenen Merge-Gates stehen in
[docs/phase-2a-qa.md](docs/phase-2a-qa.md).
Die Stable-Inventur des Travel Journals, das getrennte Datenbankdesign und die
Opt-in-Grenze des Legacy-Imports stehen in
[docs/phase-2d-travel-journal-plan.md](docs/phase-2d-travel-journal-plan.md).

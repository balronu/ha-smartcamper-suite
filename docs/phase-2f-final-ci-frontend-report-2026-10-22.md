# SmartCamper Suite – Phase 2F Prüfbericht

Datum: 2026-10-22  
Stand: `v0.3.0-beta.3`-Entwicklungsstand, finaler lokaler Branch-Commit `ac6694cbef7afd5e4902cabd328491bccb2fd9f2`  
PR: [Draft PR #8](https://github.com/balronu/ha-smartcamper-suite/pull/8)

## Änderungen

- Ressourcenpfad der Lovelace-Karte ohne Query-String korrekt als HA-Static-Path registriert.
- HA-2026.10.1-kompatible Frontend-API für zusätzliche JavaScript-Ressourcen ergänzt.
- `getConfigElement()` und `getStubConfig()` auf statische Custom-Card-Factories umgestellt.
- Editor mit `setConfig()` und Rückbefüllung bestehender Werte versehen.
- Browser-Regressionstest auf den echten statischen HA-Editor-Vertrag aktualisiert.
- Hassfest-Selector-Übersetzungen aus dem ungültigen `config.step.*.selector`-Pfad in den gültigen Top-Level-Selector-Bereich verschoben.

## Isolierter HA-Nachweis

Verwendet wurde eine separate Home-Assistant-2026.10.1-Instanz mit eigener temporärer Konfiguration und synthetischem Benutzer. Es wurden keine produktiven Systeme, VM 104 oder echte Providerzugänge verwendet.

- Config Flow über die echte HA-Flow-API abgeschlossen.
- Zwei Fahrzeuge angelegt: `Wohnmobil` mit `device_tracker.wohnmobil_zoe` und `Opel` mit eigenem synthetischem Tracker.
- Tankerkönig und Nakordoni gemeinsam aktiviert; der Tankerkönig-Zugang wurde einmal als globales Provider-Konto gespeichert und nicht pro Fahrzeug dupliziert.
- HA-Config-Entry nach Neustart erneut geladen; Frontend, Ressourcen und Dashboard waren wieder verfügbar.
- JavaScript-Ressource nach Neustart mehrfach mit HTTP 200 geladen.
- `window.customCards` enthielt `smartcamper-card`.
- Der echte HA-Kartenpicker fand `SmartCamper Suite`.
- Der Kartenkonfigurationsdialog öffnete sich; der visuelle Editor zeigte Modul-, Fahrzeug-, Layout-, Sortier-, Abruf- und Anzeige-Felder.
- Der zuvor sichtbare Fehler `Visual editor not supported` sowie `setConfig is not a function` ist behoben.

## Lokale Tests

- Python: **56 bestanden, 1 übersprungen** (`pytest`, HA 2026.10.1-Venv)
- Frontend Vitest: **6 bestanden**
- Frontend TypeScript/esbuild: **bestanden**
- Browser-Kartenregression: **bestanden**
- `git diff --check`: **bestanden**
- Isolierter HA-Flow-/Frontend-Test: **bestanden**

Die isolierte HA-Instanz wurde nach dem Test beendet. Die während des Starts sichtbaren FFmpeg-/TurboJPEG-Warnungen stammen von nicht installierten optionalen HA-Systembibliotheken und nicht von SmartCamper.

## Modul-Funktionsstand

| Modul | Stand |
|---|---|
| Camper Travel Journal | Echte SQLite-Persistenz, Fahrten-/Reise-/Stopp-/Aufenthalts-/Kosten-/Bewertungsdaten, GPX-Import, PDF-/WebSocket- und Servicepfade vorhanden. Nicht nur Darstellung. |
| Mobile Fuel Stations | Echte fahrzeugbezogene Suche, Provider-Registry, Cache, Quoten-/Fehlerstatus, Refresh- und Bewegungs-/Zeittrigger vorhanden. In diesem Test wurden Provideraufrufe ausschließlich synthetisch bzw. nicht-live geprüft. |
| Camper Route Planner | Echte fahrzeugbezogene Routenanforderung, Nakordoni-Transportgrenze, Ergebnis-/GPX-/Kartenpfade vorhanden. Kein Live-Routenaufruf mit produktiven Zugangsdaten durchgeführt. |

## GitHub-CI

Finaler Push-Lauf: [Validate 39799240289](https://github.com/balronu/ha-smartcamper-suite/actions/runs/39799240289), Commit `ac6694c`. Zum Zeitpunkt dieses Berichts waren Frontend, Home Assistant und Security grün; Hassfest und Python waren bei GitHub noch **queued**. Der vorherige Lauf [39798665223](https://github.com/balronu/ha-smartcamper-suite/actions/runs/39798665223) hatte den Frontend-Test wegen des veralteten Instanz-Aufrufs erwartbar nicht bestanden; dieser Test wurde lokal korrigiert und im finalen Lauf erfolgreich bestätigt.

## Offene Punkte und Empfehlung

- Die finale GitHub-CI ist zum Berichtszeitpunkt noch nicht vollständig abgeschlossen; Hassfest und Python müssen vor einer Merge-Entscheidung grün werden.
- Nakordoni-OAuth ist als bestehende Verbindung plus expliziter Reconfigure-/Erneuerungsflow konzipiert; ein echter OAuth-Providerdialog wurde wegen der verbindlichen No-Live-Provider-Regel nicht ausgeführt.
- Kein produktiver Legacy-Import und keine automatische Migration wurden durchgeführt.
- Kein Merge nach `main`, kein Tag und kein Release.

**Empfehlung: NO-GO für Beta-Veröffentlichung, bis der finale CI-Lauf vollständig grün ist.** Danach ist eine kontrollierte Beta fachlich vertretbar; ein produktiver Praxistest auf VM 104 bleibt eine separate Freigabeentscheidung.

Produktive Systeme, VM 104, bestehende Einzelintegrationen und produktive Datenbanken blieben unverändert.

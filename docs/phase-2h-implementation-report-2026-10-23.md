# Phase 2H – lokaler Implementierungsbericht (2026-10-23)

## Status

Die Änderungen wurden lokal auf dem Branch `phase-2h-ux-ui` auf Basis von
`v0.3.0-beta.4` implementiert. Es gab keinen Push, kein PR, keinen Merge,
kein Tag und kein Release. VM 104, produktive Provider, Stable-Integrationen
und produktive Datenbanken wurden nicht verwendet oder verändert.

## Umgesetzt

- Fahrzeugprofile bleiben die primäre Quelle der Lovelace-Fahrzeugauswahl;
  bestehende explizite `vehicle_id`-Konfigurationen und Sensor-Fallbacks
  bleiben kompatibel.
- Der Karteneditor verwendet ein Fahrzeug-Dropdown, getrennte Koordinatenfelder,
  modulabhängige Felder und ein responsives vertikales Layout. Die Editortexte
  schalten zwischen Deutsch und Englisch über die HA-Locale um.
- Config- und Options-Flow verwenden übersetzte Provider-, Fahrzeug- und
  Aktualisierungsoptionen. Das Entfernen eines Fahrzeugs verlangt eine
  Bestätigung. Neue Fahrzeuge starten mit manueller Aktualisierung.
- Globale Aktualisierungswerte werden beim Speichern konsistent auf die
  verwalteten Fahrzeugprofile angewendet, ohne Providerzugänge zu duplizieren.
- Tankerkönig, Petromap und Nakordoni liefern getrennte, geheimnisfreie
  Statusattribute. API-Fehler werden als Konfiguration, Authentifizierung,
  Berechtigung, Kontingent oder Nichterreichbarkeit unterschieden.

## Nachweise

- Python/HA: `59 passed, 1 skipped` mit Home Assistant 2026.10.1/Python 3.14.
- Ruff, JSON-Validierung, Compileall und `git diff --check`: bestanden.
- Frontend: `7 passed`, TypeScript/esbuild-Build bestanden.
- Chromium-Kartenharness: bestanden; Kartenregistrierung, Editor-Dropdown,
  modulabhängige Sichtbarkeit, Fahrzeugprofile und mobile Breite geprüft.
- Branding-/Release-Metadaten: `5 passed`.
- Der optionale Coexistence-/echte HA-Frontend-Harness wurde nicht ausgeführt,
  weil `pytest-homeassistant-custom-component` in der isolierten Umgebung fehlt.
  Der vorhandene Browserharness ist daher kein Ersatz für Kartenpicker-,
  Ressourcen-, Reload- und Neustartnachweis im echten HA-Frontend.
- `gitleaks` ist lokal nicht installiert; ein Security-CI-Lauf existiert erst
  nach einem ausdrücklich freigegebenen Push/PR.

## Offene Punkte

- HACS-Updateanzeige und offizielles Home-Assistant-Brands-System wurden nicht
  live reproduziert beziehungsweise veröffentlicht.
- Echte HA-Frontend-Interaktion mit Kartenpicker, Ressourcenregistrierung,
  Integration-Reload und Neustart bleibt vor einer Beta-Freigabe erforderlich.
- Live-Provider-, Kontingent- und Nakordoni-OAuth-Tests wurden nicht ausgeführt.
- Die drei Module besitzen die bisherige Offline-/synthetische Funktionalität;
  ein Live-Nachweis der Providerdienste ist davon getrennt.

## Empfehlung

Für die lokale Codeprüfung: **GO**. Für Push/PR, Beta-Veröffentlichung oder
produktiven Praxistest: **NO-GO**, bis der isolierte echte HA-Frontend-Harness
inklusive Picker/Reload/Neustart und die verfügbaren Security-/HACS-Gates auf
dem exakten lokalen Commit erfolgreich nachgewiesen sind.

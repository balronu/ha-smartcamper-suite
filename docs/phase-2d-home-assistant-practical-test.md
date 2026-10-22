# Vorbereitung des ersten Home-Assistant-Praxistests

**Status: NOT READY für die Ausführung.** Dieses Dokument beschreibt nur den
freigegebenen Testablauf. VM 104 wird in Phase 2D nicht verändert.

## Voraussetzungen

1. Separates HA-Test-Backup und Rückbauplan erstellen.
2. SmartCamper Suite erst nach einem separaten Installations-Approval laden.
3. Bestehende Stable-Integrationen nicht entfernen:
   Mobile Fuel Stations, Camper Route Planner und Camper Travel Journal.
4. Synthetische beziehungsweise ausdrücklich freigegebene API-Credentials
   verwenden; keine Produktionsschlüssel übernehmen.
5. Vorherige Prüfung der Datei- und Entity-Registry auf Domain-/ID-Konflikte.

## Testmatrix

- Suite-Config-Entry anlegen und zentrale Fahrzeuge mit unterschiedlichen
  Trackern einrichten.
- `fuel_stations`, `route_planner` und `travel_journal` einzeln aktivieren und
  deaktivieren.
- Je eine `custom:smartcamper-card` pro Fahrzeug und Modul anlegen.
- Reise erstellen/bearbeiten/beenden, Aufenthalt/Zwischenstopp/Kosten anlegen.
- Synthetischen GPX-Dry-Run, Import, Wiederholungsimport und PDF-Download
  prüfen.
- Route/GPX und Tankstellensuche weiterhin ausführen.
- HA-Reload und Neustart simulieren; Static Paths, WebSocket-Kommandos,
  Sensoren und Ressourcen auf Duplikate prüfen.
- Prüfen, dass die Legacy-Journal-Datenbank nicht geöffnet oder verändert wird
  und dass die Suite-Datei getrennt bleibt.

## Rückbau

1. Suite-Config-Entry entladen.
2. Suite-Dateien und Entity-Registry-Einträge nur nach dokumentierter
   Freigabe entfernen.
3. Legacy-Integrationen unverändert weiterbetreiben.
4. Dashboard-Karten auf den vorherigen Stand zurücksetzen.
5. Keine automatische Datenmigration rückgängig machen müssen: Der Import ist
   explizit und die Quelle bleibt unverändert.

## Fehlerdiagnose

Zuerst Config-Entry- und HA-Log prüfen, danach die Suite-Sensorattribute,
WebSocket-Registrierung und die beiden SQLite-Pfade vergleichen. Keine
Credentials oder vollständigen GPS-Daten in Logs oder Tickets kopieren.

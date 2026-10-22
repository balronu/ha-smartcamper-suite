# Phase 2D – Camper Travel Journal v0.3.2

Referenz: `balronu/ha-camper-travel-journal` Stable `v0.3.2`, Commit
`11a98f966110d2e70aeb5181b66bc4d97c373623`.

Das Quellrepository bleibt unverändert. Die Suite verwendet die zentrale
Fahrzeugverwaltung und eine eigene Datei
`.storage/smartcamper_suite_travel_journal.sqlite`; die Legacy-Datenbank wird
weder automatisch gesucht noch geöffnet.

## Funktionsmatrix

| Stable-Funktion | Suite-Stand | Nachweis/Abweichung |
|---|---|---|
| Reisen erstellen, bearbeiten, löschen | übernommen | `JournalStore`, HA-Services und WebSocket `smartcamper_suite/journal/*` |
| Reisebeginn/-ende und Status | übernommen | `planned`, `active`, `completed`, `cancelled` |
| Aufenthalte | übernommen | eigene Tabelle und CRUD-Grundlage |
| Zwischenstopps | übernommen | eigene Tabelle, Reise-/Fahrzeugbezug |
| Kosten/Kategorien | übernommen | Centbeträge, EUR/ISO-Währung, validierte Kategorien |
| Zentrale Fahrzeugzuordnung | übernommen | keine zweite Fahrzeugverwaltung |
| GPS-Punkte | übernommen | getrennte Tabelle, deduplizierte Koordinaten; keine Hintergrundaufzeichnung ohne Modulfreigabe |
| Reiseübersicht/Summen | übernommen | Journal-Sensor je Fahrzeug |
| Diagnose | übernommen | authentifizierte Suite-WebSocket-Antwort plus Sensorattribute, ohne Secrets |
| GPX-Analyse und Import | übernommen | offline parser, Hash-Idempotenz, Punktvalidierung und Trip-Zuordnung |
| PDF-Bericht | teilweise übernommen | gültiger mehrseitiger Offline-PDF-Export mit Reise-, Aufenthalts-, Stopp-, Kosten- und GPS-Abschnitten; historisches ReportLab-Layout nicht 1:1 reproduziert |
| Reverse-Geocoding | übernommen | Suite-eigener Cache mit injizierbarem Provider-Resolver; keine Live-Anfrage in Tests |
| Aufenthaltsvorschläge | übernommen | zeit-/entfernungsbasierte synthetische Vorschläge mit Accept/Dismiss |
| Übernachtungsdaten und Bewertungen | übernommen | normalisierte Tabellen, Validierung und CRUD-Grundlage |
| Editor/Kartenansicht | teilweise übernommen | gemeinsame Karte und Modulwahl; historische Detail-Editoren noch offen |
| Übersetzungen | teilweise übernommen | Kerntexte vorhanden; vollständige Stable-Textabdeckung noch offen |
| Legacy-Import | sicherer Opt-in-Pfad | Dry-run, Schema-/Hashprüfung, Idempotenz, ID-Mapping, unveränderte Quelle |

## Datenbank- und Importgrenzen

- Schema-Version 4, WAL, Foreign Keys, Busy Timeout und transaktionale CRUDs.
- GPX-Fahrten persistieren geordnete GPS-Punktreferenzen in `drive_gps_points`; der
  Route-Endpunkt liefert die gespeicherte Geometrie inklusive Start-/Endkoordinaten.
- Kein automatisches Öffnen einer `camper_travel_journal`-Datenbank.
- Import ist ohne `opt_in=True` gesperrt.
- Dry-run erzeugt nur eine Vorschau; wiederholte Importe werden über den
  SHA-256-Quellhash erkannt.
- Rollback erfolgt durch die SQLite-Transaktion bei Validierungs- oder
  Schreibfehlern. Die Legacy-Datei wird ausschließlich im Read-only-Modus
  geöffnet.
- Unklare Fahrzeugzuordnungen werden nicht automatisch zusammengeführt;
  `vehicle_map` muss explizit übergeben werden.

## Noch offene Parität

Die Suite deckt jetzt 32 authentifizierte Journal-WebSocket-Kommandos ab,
einschließlich Fahrzeugliste, Diagnostik, Trips, Routen-Segmente, manuelle
Fahrten, Stopps, Kosten, GPX, PDF, Vorschläge, Übernachtungen und Bewertungen.
Die Stable-Integration registriert 31 Kommandos; die Suite verwendet für
Vorschläge und Übernachtungen teilweise bewusst sprechendere Namen
(`list_suggestions`/`generate_suggestions`/`accept_suggestion` sowie
`upsert_overnight`/`upsert_rating`) statt der historischen Stable-Namen.
Einzelne Stable-Felder und Antwortformate, insbesondere alle historischen
Detail-Editoren und die vollständige Stable-Parametersemantik, sind noch nicht
vollständig gleichwertig abgebildet. Diese Lücke ist ein NO-GO für vollständige
Stable-Parität.

Der PDF-Export ist ein dependency-freier, mehrseitiger Suite-Bericht mit den
wesentlichen Journal-Daten; er übernimmt noch nicht jedes historische
ReportLab-Layout der Einzelintegration.
Reverse-Geocoding verwendet einen injizierten gemeinsamen Provider-Resolver;
die Suite führt keine ungeprüften Live-Endpunkte ein. Historische Spezial-
Editorflächen der Einzelintegration werden in der gemeinsamen Karte über
WebSocket- und Service-Verträge abgebildet, nicht als separate Karten kopiert.

## Reproduzierbarer Koexistenztest

Der lokale Test `tests/test_real_coexistence.py` verwendet den offiziellen
`async_test_home_assistant`-Helper, eine temporäre Konfiguration und die
read-only Stable-Checkouts. Er initialisiert HTTP, WebSocket und die
Frontend-URL-Verwaltung, lädt anschließend `mobile_fuel_stations`,
`camper_route_planner`, `camper_travel_journal` und eine echte Suite-
Config-Entry. Ausführung:

```text
SMARTCAMPER_RUN_COEXISTENCE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  ./.venv/bin/python -m pytest -q -rs tests/test_real_coexistence.py
```

Ergebnis des aktuellen lokalen Laufs: **1 bestanden**. Der Test erzeugt nur
eine temporäre Suite-Datenbank und verändert keine Legacy-Datei. Der
`pytest_homeassistant_custom_component`-Pluginpfad bleibt wegen einer
inkompatiblen Abhängigkeit zu HA 2026.10.1 deaktiviert; der zugrunde liegende
offizielle Helper wird direkt verwendet.

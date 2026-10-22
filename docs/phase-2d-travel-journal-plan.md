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
| Diagnose | übernommen | Sensorattribute ohne Secrets |
| GPX-Analyse und Import | übernommen | offline parser, Hash-Idempotenz, Punktvalidierung und Trip-Zuordnung |
| PDF-Bericht | übernommen | dependency-freier gültiger Offline-PDF-Export über WebSocket |
| Reverse-Geocoding | übernommen | Suite-eigener Cache mit injizierbarem Provider-Resolver; keine Live-Anfrage in Tests |
| Aufenthaltsvorschläge | übernommen | zeit-/entfernungsbasierte synthetische Vorschläge mit Accept/Dismiss |
| Übernachtungsdaten und Bewertungen | übernommen | normalisierte Tabellen, Validierung und CRUD-Grundlage |
| Editor/Kartenansicht | übernommen | gemeinsame `custom:smartcamper-card`, Journal-Ansicht und Editor-Modulwahl |
| Übersetzungen | Suite-Struktur vorhanden | Journal-spezifische Texte werden mit der Kartenansicht weiter vervollständigt |
| Legacy-Import | sicherer Opt-in-Pfad | Dry-run, Schema-/Hashprüfung, Idempotenz, ID-Mapping, unveränderte Quelle |

## Datenbank- und Importgrenzen

- Schema-Version 1, WAL, Foreign Keys, Busy Timeout und transaktionale CRUDs.
- Kein automatisches Öffnen einer `camper_travel_journal`-Datenbank.
- Import ist ohne `opt_in=True` gesperrt.
- Dry-run erzeugt nur eine Vorschau; wiederholte Importe werden über den
  SHA-256-Quellhash erkannt.
- Rollback erfolgt durch die SQLite-Transaktion bei Validierungs- oder
  Schreibfehlern. Die Legacy-Datei wird ausschließlich im Read-only-Modus
  geöffnet.
- Unklare Fahrzeugzuordnungen werden nicht automatisch zusammengeführt;
  `vehicle_map` muss explizit übergeben werden.

## Bewusste Abweichungen

Der PDF-Export ist ein dependency-freier, synthetischer Suite-Bericht und
übernimmt noch nicht jedes historische ReportLab-Layout der Einzelintegration.
Reverse-Geocoding verwendet einen injizierten gemeinsamen Provider-Resolver;
die Suite führt keine ungeprüften Live-Endpunkte ein. Historische Spezial-
Editorflächen der Einzelintegration werden in der gemeinsamen Karte über
WebSocket- und Service-Verträge abgebildet, nicht als separate Karten kopiert.

# Phase 2B – v0.8.4-Feature-Matrix

Vergleich der verifizierten Mobile-Fuel-Stations-Referenz v0.8.4 mit dem
Suite-Kandidaten. “Nachgewiesen” bedeutet: durch einen synthetischen Test,
einen HA-Fixture-Test oder einen Frontend-Test abgedeckt.

| v0.8.4-Funktion | Suite-Kandidat | Nachweis/Abweichung |
|---|---|---|
| Tankstellenname, Marke | Nachgewiesen | FuelStation, Sensor und Card |
| Preis je ausgewähltem Kraftstoff | Nachgewiesen | Provider-Contract und Kartenrendering |
| Mehrfach-Kraftstoffauswahl | Nachgewiesen | Fahrzeugprofil iteriert über fuel_types |
| Diesel, E5, E10, LPG | Nachgewiesen | Capability-Contract; nur verifizierte Mappings |
| HVO100 | Bewusst nicht erfunden | Kein Quellprovider liefert bestätigte Preise |
| Entfernung und Adresse | Nachgewiesen | Adapternormalisierung und Kartenattribute |
| Öffnungsstatus | Nachgewiesen | is_open oder “unbekannt” |
| Individueller Radius | Nachgewiesen | pro Fahrzeug, maximal 25 km |
| Ergebnisanzahl | Nachgewiesen | pro Fahrzeug, 1–10 |
| Provider-Auswahl | Nachgewiesen | fuel_provider_modes |
| Auto-/Fallback-Modus | Teilweise nachgewiesen | Reihenfolge und sichere Transport-Fallbacks; Länder-/Quota-Policy offen |
| Fehlende Preise | Nachgewiesen | Preis wird als “–” dargestellt |
| Provider nicht verfügbar | Nachgewiesen | Status/Error-State und Fallback-Contract |
| Loading-/Empty-/Error-State | Nachgewiesen | Runtime-Statusmodell und Kartenrenderer |
| Sortierung Distanz/Preis | Nachgewiesen | Runtime und Kartenrenderer unterstützen beide Sortiermodi |
| Aktualisierung | Teilweise | Sensor-Updatepfad vorhanden; adaptive Bewegung folgt |
| Persistenter Cache | Teilweise | Account-/Fahrzeug-Key und Deduplizierung; TTL folgt |
| Rate-Limits/Credits | Contract vorhanden | 429/Provider-Ausfall klassifiziert; Telemetrie nicht vollständig |
| Nakordoni OAuth2-PKCE | HA-Integration vorhanden | Exakte Stable-Implementierung/URLs, HA-Refresh-Lock und synthetische PKCE-Vertragsprüfung; E2E ohne Credential nicht durchgeführt |
| Marktberechtigungen | Teilweise | markets_* aus Token-/Accountdaten steuern Auto-Auswahl; providerseitige Usage-Abfrage/Quota-Telemetrie folgt |
| Legacy-Config-Import | Nachgewiesen | Opt-in, idempotent, secret-frei, transaktionaler Commit und Rollback |
| Legacy-Lovelace-Import | Preview-only | Karten werden nicht automatisch verändert |
| Drei Lovelace-Modi | Teilweise | display_mode/editor vorhanden; historische Highlights-/Logo-/Diagnoseoptionen bleiben offen |
| Mehrere Karten/Fahrzeuge | Nachgewiesen | Explizite Fahrzeug-ID und getrennte Sensorattribute |

## Bewusste Grenzen

Die Suite macht keine Preise oder Länderberechtigungen durch Annahmen sichtbar.
Insbesondere HVO100 und Nakordoni-Autoauswahl ohne bestätigte Marktmetadaten
bleiben deaktiviert. Diese Matrix ist Bestandteil des PR-Reviews und wird vor
einem GO aktualisiert.

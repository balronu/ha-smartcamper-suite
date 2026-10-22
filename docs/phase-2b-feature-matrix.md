# Phase 2B – v0.8.4-Feature-Matrix

Vergleich der verifizierten Mobile-Fuel-Stations-Referenz v0.8.4 mit dem
Suite-Kandidaten. “Nachgewiesen” bedeutet: durch einen synthetischen Test,
einen HA-Fixture-Test oder einen Frontend-Test abgedeckt.

| v0.8.4-Funktion | Suite-Kandidat | Nachweis/Abweichung |
|---|---|---|
| Tankstellenname, Marke | Nachgewiesen | FuelStation, Sensor und Card; Logo-URL plus Fallback |
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
| Highlights/Hervorhebungen | Nachgewiesen | Highlights-Layout verwendet die zwei priorisierten Ergebnisse |
| Navigation | Nachgewiesen | Apple Maps, Google Maps, Waze oder automatischer Google-Fallback |
| Anbieterlogos | Nachgewiesen | 60 verifizierte v0.8.4-PNG-Assets werden unter `/smartcamper_suite/logos/` statisch und idempotent ausgeliefert; unbekannte Marken haben einen Fallback |
| Diagnostik/Quota-Anzeige | Teilweise | Secret-freie Usage-Projektion für Nakordoni; Providerfehler und unbekannte Quoten sichtbar |
| Aktualisierung | Teilweise | Manuelle Karten-/Service-Aktualisierung und Sensorpfad; die historische automatische/bewegungsabhängige Koordination ist noch nicht vollständig portiert |
| Persistenter Cache | Teilweise | Account-/Fahrzeug-Key und Deduplizierung; TTL folgt |
| Rate-Limits/Credits | Teilweise nachgewiesen | 429/Provider-Ausfall, gemeinsamer Cache und Nakordoni-Usage/Quota; nicht dokumentierte Fremdquoten bleiben unbekannt |
| Nakordoni OAuth2-PKCE | Nachgewiesen synthetisch | Exakte Stable-Implementierung/URLs, HA-Refresh-Lock und lokaler PKCE-/Revoke-Testserver; kein echter Providerzugang |
| Marktberechtigungen | Teilweise | `markets_approved`/`markets_granted`/`markets_available`/`markets_allowed` werden ohne Annahmen ausgewertet; providerseitige Länder-/Quota-Policies bleiben dort unbekannt, wo die API sie nicht liefert |
| Legacy-Config-Import | Nachgewiesen | Opt-in, idempotent, secret-frei, transaktionaler Commit und Rollback |
| Legacy-Lovelace-Import | Preview-only | Karten werden nicht automatisch verändert |
| Drei Lovelace-Modi | Teilweise | display_mode, Layoutfamilien, Logos, Highlights, Navigation und Editor vorhanden; vollständige historische CSS-/Refresh-/Diagnostikparität bleibt offen |
| Mehrere Karten/Fahrzeuge | Nachgewiesen | Explizite Fahrzeug-ID und getrennte Sensorattribute |

## Bewusste Grenzen

Die Suite macht keine Preise oder Länderberechtigungen durch Annahmen sichtbar.
Insbesondere HVO100 und Nakordoni-Autoauswahl ohne bestätigte Marktmetadaten
bleiben deaktiviert. Diese Matrix ist Bestandteil des PR-Reviews und wird vor
einem GO aktualisiert.

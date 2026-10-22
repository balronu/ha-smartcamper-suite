# Phase 2C – Camper Route Planner

## Referenz

Die Implementierung basiert auf dem unveränderten Stable-Tag `v0.1.0` des
Repositories [balronu/ha-camper-route-planner](https://github.com/balronu/ha-camper-route-planner),
Commit `8a34f5e7e96279243813b3fe277b1abf88639b0e`. Das Quellrepository wird
nicht geändert und bleibt eine eigenständige Integration.

## Stable-Funktionsmatrix

| Funktion in v0.1.0 | Suite-Übernahme | Nachweis/Abgrenzung |
|---|---|---|
| Fahrzeugprofile mit Länge, Breite, Höhe, Gewicht, Achsen | übernommen | zentrale `Vehicle`-Profile; keine Doppelprofile |
| mehrere Fahrzeuge und GPS-Entitäten | übernommen | `vehicle_id` ist Teil jedes Requests und Sensors |
| Nakordoni Truck-/Motorhome-Parameter | übernommen, Beta-markiert | dimensionsbasierter Adapter; Live-Transport bleibt explizit konfiguriert |
| Start, Ziel und bis zu fünf Via-Punkte | übernommen | WGS84-Validierung und deterministischer Cache-Key |
| Alternativen und Verkehrsmodus | übernommen | Request-Schema, offline reproduzierbar |
| Länder, Restriktionen und Mautmetadaten | übernommen | unbekannte Werte bleiben unbekannt; Maut wird nicht als verbindlicher Wohnmobilpreis dargestellt |
| Warnung über 3,5 t, Schweiz und Durchfahrtsverbote | übernommen | sichtbare Providerwarnungen; keine Rechtsgarantie |
| GPX Route, Track und Combined | übernommen | reiner lokaler Export, kein Providerzugriff |
| Sygic-Übergabe | vorbereitet | GPX ist der konservative Übergabepfad; kein unbestätigter Deep-Link |
| Kartenansicht | übernommen | `custom:smartcamper-card` zeigt Geometrie, Distanz, Dauer und Warnungen |
| visueller Editor | übernommen | Modul, Fahrzeug sowie Start/Ziel als JSON-Punkte |
| automatische Routenberechnung | bewusst nicht übernommen | Berechnung ausschließlich durch explizite Aktion, um Quoten und Kosten zu schützen |
| Kartenkacheln/Geocoding | Suite-Grenze | vorhandene zentrale Provider-Registry; keine zweiten Credential-Speicher |

## Architektur

`RoutePlannerRuntime` nutzt die zentralen Suite-Fahrzeuge und löst den
Provider-Zugang aus `CredentialStore`/`provider_accounts` auf. Der
`RouteCoordinator` dedupliziert identische parallele Requests, cached nach
allen routenbestimmenden Eingaben und zählt das Kontingent auf Provider-/Account-
Ebene. Deaktivierte Module starten keinen Timer und keine Route-Abfrage.

Der aktuell übernommene Nakordoni-Vertrag ist technisch nur als Beta-/Mock-
Grenze belastbar. Die Oberfläche zeigt deshalb immer den Beta-/Warnstatus;
Länderrecht, Maut, Schweizer Abgaben, 3,5-t-Grenzen und Verkehrszeichen müssen
vor einer produktiven Navigation zusätzlich geprüft werden.

## Abnahme Phase 2C

- [x] Branch basiert auf dem Phase-2B-Merge.
- [x] Zentrale Fahrzeug- und Credential-Verwaltung verwendet.
- [x] Mehrfahrzeug-Identität, Validierung, Cache und Quota-Guard getestet.
- [x] GPX-Export offline und ohne Secrets getestet.
- [x] Suite-Karte um Route-Ansicht und Editor-Grundlage erweitert.
- [ ] Echtes Nakordoni-Motorhome-Produkt und reale Länder-/Mautsemantik: Providerfreigabe und Live-Vertrag erforderlich.
- [ ] Sygic-Gerätetest: Android/iOS und Truck-&-Caravan-App nicht Teil des Offline-CI.

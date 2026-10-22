# Verifizierte Stable-Ausgangsbasis

Abgerufen am 22.10.2026 über die GitHub-Releases-, Tag- und Actions-API.
Die Commit-SHA ist bei den annotierten Tags das aufgelöste Tag-Ziel.

| Projekt | Stable | Datum | Tag-Ziel | HA-Domain | CI-Nachweis |
|---|---|---|---|---|---|
| Mobile Fuel Stations | 0.8.4 | 2026-10-21 | `13da23a87d10af753d68af51bfee9694446c1036` | `mobile_fuel_stations` | Tests + Validate erfolgreich, Run 39578606007 / 39578605922 |
| Camper Travel Journal | 0.3.2 | 2026-10-20 | `11a98f966110d2e70aeb5181b66bc4d97c373623` | `camper_travel_journal` | Tests + Validate erfolgreich, Run 39443668283 / 39443668398 |
| Camper Route Planner | 0.1.0 | 2026-10-22 | `8a34f5e7e96279243813b3fe277b1abf88639b0e` | `camper_route_planner` | Main + Tag Validate erfolgreich, Run 39747126761 / 39747326889 |

Releases: [Mobile Fuel Stations](https://github.com/balronu/ha-mobile-fuel-stations/releases/tag/v0.8.4), [Camper Travel Journal](https://github.com/balronu/ha-camper-travel-journal/releases/tag/v0.3.2), [Camper Route Planner](https://github.com/balronu/ha-camper-route-planner/releases/tag/v0.1.0).

Relevant interfaces are the three Config Flows, Lovelace card/resource
bundles, provider-specific HTTP clients, vehicle profiles and (for Travel
Journal) its private SQLite persistence. The source manifests confirm MIT
licensing. This repository therefore starts with MIT and does not copy source
code or credentials from the predecessors.

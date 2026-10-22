# SmartCamper Suite

**Phase 2D development — not a production release.**

<p align="center"><img src="docs/assets/smartcamper-suite-logo-set.png" alt="SmartCamper Suite logo set" width="720"></p>

SmartCamper Suite – A modular Home Assistant integration for motorhome travel
journals, fuel stations, route planning and border wait-time forecasts.

SmartCamper Suite is one modular Home Assistant custom integration using the
`smartcamper_suite` domain. It establishes shared vehicle and provider
boundaries, credential status handling, offline-testable API policies,
versioned isolated storage, four independent module runtimes, and the
foundation for `custom:smartcamper-card`.

The `fuel_stations` module now contains offline-testable Tankerkönig, Petromap
and Nakordoni adapters, vehicle-scoped search settings, shared provider
credentials, provider fallback, per-vehicle sensors and the fuel-stations view
in `custom:smartcamper-card`. The card includes multi-fuel prices, sorting,
highlights, navigation, provider logos, diagnostics, automatic/movement-based
refresh and manual refresh. OAuth refresh and legacy migration are tested as
isolated candidate paths; no legacy entry is changed automatically.

This remains development code: it does not open or migrate productive data,
use real credentials, perform live API calls in tests, or install anything in
Home Assistant VM 104.

The `route_planner` module uses the shared vehicle profiles and provides
explicit route calculation, interactive start/destination/waypoint editing,
visible beta/restriction/toll warnings, and GPX route/track/combined downloads.
Nakordoni motorhome routing is not presented as legally validated navigation;
automatic background routing is intentionally disabled. Details are in
[docs/phase-2c-route-planner-plan.md](docs/phase-2c-route-planner-plan.md).

The `travel_journal` module also uses only the central vehicle profiles. It
provides the core trip, stay, stop and expense operations, vehicle-scoped
journal sensors, and a separate versioned SQLite file. Legacy import is only
available through explicit opt-in preview/import operations with SHA-256
idempotency; the old database is opened read-only and never changed
automatically. The Stable feature matrix and intentionally open adapters are
documented in [docs/phase-2d-travel-journal-plan.md](docs/phase-2d-travel-journal-plan.md).
The first isolated Home Assistant practical-test preparation is documented in
[docs/phase-2d-home-assistant-practical-test.md](docs/phase-2d-home-assistant-practical-test.md).

The QA report and current merge gates are documented in
[docs/phase-2a-qa.md](docs/phase-2a-qa.md).
The Phase 2B implementation plan and deviations are documented in
[docs/phase-2b-mobile-fuel-stations-plan.md](docs/phase-2b-mobile-fuel-stations-plan.md).
The detailed v0.8.4 comparison is documented in
[docs/phase-2b-feature-matrix.md](docs/phase-2b-feature-matrix.md).

## Modules

| Module | Illustration | Status |
|---|---|---|
| Camper Travel Journal | [Travel journal](docs/assets/module-travel-journal.svg) | Phase 2D core functions; tested offline |
| Mobile Fuel Stations | [Fuel stations](docs/assets/module-fuel-stations.svg) | Phase 2B candidate; tested offline |
| Camper Route Planner | [Route planning](docs/assets/module-route-planner.svg) | Phase 2C candidate; tested offline |
| Wartezeiten Forecast | [Border wait times](docs/assets/module-border-forecast.svg) | Placeholder; not implemented in Phase 2B |

Branding paths and approved-artwork provenance are documented in
[docs/branding.md](docs/branding.md).

The browser regression test runs with `npm run browser:test` and uses only
synthetic Home Assistant state.

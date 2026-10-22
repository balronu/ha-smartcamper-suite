# SmartCamper Suite

**Phase 2B development — not a production release.**

SmartCamper Suite is one modular Home Assistant custom integration using the
`smartcamper_suite` domain. It establishes shared vehicle and provider
boundaries, credential status handling, offline-testable API policies,
versioned isolated storage, four independent module runtimes, and the
foundation for `custom:smartcamper-card`.

The `fuel_stations` module now contains offline-testable Tankerkönig, Petromap
and Nakordoni adapters, vehicle-scoped search settings, shared provider
credentials, provider fallback, per-vehicle sensors and the fuel-stations view
in `custom:smartcamper-card`. The card includes multi-fuel prices, sorting,
highlights, navigation, provider logos, diagnostics and manual refresh. OAuth
refresh and legacy migration are tested as isolated candidate paths; no legacy
entry is changed automatically.

This remains development code: it does not open or migrate productive data,
use real credentials, perform live API calls in tests, or install anything in
Home Assistant VM 104.

The QA report and current merge gates are documented in
[docs/phase-2a-qa.md](docs/phase-2a-qa.md).
The Phase 2B implementation plan and deviations are documented in
[docs/phase-2b-mobile-fuel-stations-plan.md](docs/phase-2b-mobile-fuel-stations-plan.md).
The detailed v0.8.4 comparison is documented in
[docs/phase-2b-feature-matrix.md](docs/phase-2b-feature-matrix.md).

The browser regression test runs with `npm run browser:test` and uses only
synthetic Home Assistant state.

# SmartCamper Suite

**Phase 2B development — not a production release.**

SmartCamper Suite is a single modular Home Assistant custom integration under
the domain `smartcamper_suite`. It provides one shared vehicle registry,
provider/account boundary, credential abstraction, offline API infrastructure,
versioned suite storage, four isolated module runtimes, and the foundation for
`custom:smartcamper-card`.

## Current scope

The `fuel_stations` module now provides offline-testable Tankerkönig, Petromap
and Nakordoni adapters, vehicle-scoped search settings, shared provider
credentials, provider fallback, per-vehicle sensors and the fuel-stations view
in `custom:smartcamper-card`. OAuth refresh and legacy migration are tested as
isolated candidate paths; no legacy entry is changed automatically.

This is still development code. It does not open or migrate a productive
database, use real credentials, perform live API calls in tests, or install
anything in Home Assistant VM 104.

Modules: `travel_journal`, `fuel_stations`, `route_planner`, and
`border_forecast`. Only `fuel_stations` has Phase-2B candidate functionality;
the other three remain isolated placeholders and all modules stay disabled by
default.

## Development

```bash
python -m pytest
python -m compileall custom_components tests
ruff check .
cd frontend && npm ci && npm test && npm run build
```

See [README.en.md](README.en.md), [docs/architecture.md](docs/architecture.md)
and [docs/development.md](docs/development.md).
The implementation plan and deviations are in
[docs/phase-2b-mobile-fuel-stations-plan.md](docs/phase-2b-mobile-fuel-stations-plan.md).
The detailed v0.8.4 comparison is in
[docs/phase-2b-feature-matrix.md](docs/phase-2b-feature-matrix.md).
The QA status and remaining merge gates are in
[docs/phase-2a-qa.md](docs/phase-2a-qa.md).

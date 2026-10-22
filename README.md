# SmartCamper Suite

**Phase 2A foundation — not a complete camper solution.**

SmartCamper Suite is a single modular Home Assistant custom integration under
the domain `smartcamper_suite`. It provides one shared vehicle registry,
provider/account boundary, credential abstraction, offline API infrastructure,
versioned suite storage, four isolated module runtimes, and the foundation for
`custom:smartcamper-card`.

## Current scope

This branch implements architecture and testable foundations only. It does not
read or migrate any legacy Travel Journal database, perform live API calls,
run OAuth flows, create productive vehicle profiles, or install anything in
Home Assistant VM 104.

Modules: `travel_journal`, `fuel_stations`, `route_planner`, and
`border_forecast`. They are disabled by default and contain no live feature
implementation in Phase 2A.

## Development

```bash
python -m pytest
python -m compileall custom_components tests
ruff check .
cd frontend && npm ci && npm test && npm run build
```

See [README.en.md](README.en.md), [docs/architecture.md](docs/architecture.md)
and [docs/development.md](docs/development.md).
The QA status and remaining merge gates are in
[docs/phase-2a-qa.md](docs/phase-2a-qa.md).

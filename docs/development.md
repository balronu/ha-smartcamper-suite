# Development notes

The `phase-2a-foundation` branch is the implementation branch for the initial
PR. No stable/beta release is created in Phase 2A. Tests use in-memory storage,
fake transports and synthetic vehicle data. They must not contain real API
keys, OAuth tokens, GPS profiles from production, or live provider calls.

The frontend is intentionally a placeholder. It identifies the selected
module and vehicle, and clearly labels the view as development-only. Full
module views and migration are Phase 2B+ decisions.

## Phase 2A QA commands

The local lifecycle environment uses Python 3.13.5 and HA 2025.12.5. CI also
runs Python 3.14.2 with HA 2026.10.1, which is the authoritative current-version
check.

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=. .venv/bin/python -m pytest -q
.venv/bin/ruff check .
.venv/bin/python -m compileall -q custom_components tests
python3 -m json.tool custom_components/smartcamper_suite/manifest.json >/dev/null
python3 -m json.tool hacs.json >/dev/null
git diff --check
cd frontend && npm test && npm run build
```

The available `pytest-homeassistant-custom-component` 0.2.1 plugin is not
compatible with the installed HA auth-provider API, so it is not loaded. The
tests use Home Assistant's real core classes and synthetic transports instead.

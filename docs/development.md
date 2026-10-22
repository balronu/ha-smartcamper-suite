# Development notes

The `phase-2a-foundation` branch is the implementation branch for the initial
PR. No stable/beta release is created in Phase 2A. Tests use in-memory storage,
fake transports and synthetic vehicle data. They must not contain real API
keys, OAuth tokens, GPS profiles from production, or live provider calls.

The frontend is intentionally a placeholder. It identifies the selected
module and vehicle, and clearly labels the view as development-only. Full
module views and migration are Phase 2B+ decisions.

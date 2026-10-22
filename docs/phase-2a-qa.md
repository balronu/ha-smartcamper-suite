# Phase 2A QA report

Status: candidate QA for PR #1; no merge, release, HACS publication, or
productive Home Assistant change was performed.

## Environment

- Repository branch: `phase-2a-foundation`
- Local isolated environment: Python 3.13.5, Home Assistant 2025.12.5,
  pytest 8.4.2, Ruff 0.17.1, Node/npm from the repository frontend toolchain
- HA 2026.10.1 requires Python 3.14.2 and could not be run on this host's
  Python 3.13 environment. CI provisions Python 3.14.2 and pins HA 2026.10.1.

## Results

| Area | Result | Evidence |
| --- | --- | --- |
| HA setup/unload | PASS locally | Real `HomeAssistant`, executor, ConfigEntry and SQLite path |
| Config/Options Flow and single instance | PASS locally | Synthetic flow inputs, no credentials |
| Module lifecycle/isolation | PASS locally | Four module names and injected failure |
| Vehicle persistence | PASS locally | Two IDs, distinct trackers, archive, reopen |
| Provider registry | PASS locally | All six requested providers and distinct services |
| Credentials | PASS locally | Replace/remove and secret-free public status |
| SQLite malformed/repeated init | PASS locally | Synthetic files only; no legacy DB opened |
| Frontend resource reload | PASS locally | One static route over repeated register/unregister |
| Frontend Vitest/build | PASS | 2 Vitest tests and TypeScript/esbuild build |
| Ruff/compileall/JSON/diff | PASS locally | Commands in `docs/development.md` |
| Hassfest | CI job added; pending | No local Hassfest binary |
| Secret scan | CI job added; pending | No local Gitleaks binary |

## Fixed defects

1. Setup constructed `SuiteRuntime` without its required store.
2. Setup did not create HA's `.storage` directory before SQLite.
3. Unload did not close the suite SQLite connection.
4. Frontend reloads could register the same static HTTP route more than once.
5. Options Flow assigned HA's read-only `config_entry` property in its
   constructor; it now uses the current flow API.
6. The manifest now declares its `hub` integration type.

## Explicit limitations

- OAuth token refresh and concurrent refresh locking are only data-model
  groundwork; no token refresh is reported as functional.
- Provider transports remain disabled. No API key, OAuth token, or live
  provider request was used.
- Full module functionality, legacy migration, entities, services, and
  production data migration remain Phase 2B scope.
- The local run uses HA 2025.12.5; the pinned HA 2026.10.1 CI job must pass.

## Decision

**NO-GO until CI completes the new Home Assistant 2026.10.1, Hassfest, and
security jobs successfully.** PR #1 remains open and must not be merged by
this task.

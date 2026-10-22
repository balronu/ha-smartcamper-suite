# SmartCamper Suite – Phase 2D implementation report

Status: **local candidate, not ready for beta**

## Implemented locally

- Provider selection is independent of vehicles; only enabled providers get credential fields.
- Existing API-key records remain stored when a provider is temporarily disabled. Blank password fields do not replace a stored key.
- A single Suite Config Entry now manages a persistent vehicle list. The Options Flow can add, edit, and remove vehicles while preserving stable vehicle IDs and global provider accounts.
- GPS uses a `device_tracker` EntitySelector, fuels use a multi-select selector, axle count uses a bounded dropdown, and optional dimensions/weight no longer default to zero.
- Config Flow and Options Flow are separated into provider access, provider credentials, vehicle management, modules, and refresh/general settings.
- German and English flow translations cover the new sections and fuel choices.
- The Lovelace picker metadata remains registered with the bare `smartcamper-card` tag, and `getStubConfig()` no longer inserts `type`; the rendered card configuration still uses `type: custom:smartcamper-card`.
- A regression test covers two vehicles, shared provider access, editing one vehicle, and removing the other.

## Verification

- Python/HA fixture suite: **55 passed, 1 skipped** in local HA 2026.2.3.
- Ruff, compileall, JSON validation, and `git diff --check`: **passed**.
- Frontend Vitest: **6 passed**.
- TypeScript/build: **passed**.
- Chromium card/picker/editor harness: **passed**.
- Hassfest: **not run**; no local Hassfest executable/module is available.
- Gitleaks: **not run locally**; no local binary is available.
- Required HA 2026.10.1 fixture run: **not run locally**. The available virtual environment is HA 2026.2.3, so its result is not evidence for the target version.

## Known limitations and open decisions

- The candidate intentionally keeps one parent Config Entry and an embedded vehicle list. HA Config Subentries were not introduced without a proven migration/runtime contract; existing entries and entity IDs therefore remain compatible. A subentry migration is a separate design decision.
- Nakordoni OAuth remains supported in the initial Config Flow and existing token/runtime path. The Options Flow does not expose a new OAuth authorization button; it preserves an existing OAuth token and manages API-key providers. A reauthorization UX needs a dedicated HA OAuth-flow decision.
- No live API keys, provider calls, VM 104, Proxmox, productive Home Assistant, installed HACS copy, legacy database, or external repository were changed.
- No push, PR, tag, release, or beta publication was performed.

## Recommendation

Do not prepare or publish a new beta yet. First run the candidate through HA 2026.10.1 CI/Hassfest/security gates and a real isolated HA frontend flow test covering reload and restart persistence. Only after those gates and the approved manual test should release preparation be considered.

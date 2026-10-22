# Architektur / Architecture

The integration has one Config Entry and one `SuiteRuntime`. The runtime owns
the provider registry, credential store, API transport boundary, module
manager, and a separate versioned SQLite file. Vehicles contain stable UUIDs;
credentials belong to providers/accounts and are never copied into vehicles.

Each module has an explicit setup/unload lifecycle. A module exception is
recorded on that runtime and does not abort independent modules. API calls are
disabled unless a test transport is injected. Provider service policies are
per-service because cache, quota, timeout and terms differ.

Home Assistant's Config Entry data/options are not an encrypted secret vault.
Phase 2A stores only non-secret references in the entry; the credential
adapter keeps secret values out of diagnostics and public serialization. A
future production adapter must use Home Assistant's supported secret/credential
mechanisms and document their actual protection boundaries.

The SQLite store is suite-owned and created only at runtime setup. It is not
the legacy Travel Journal database and no migration path is enabled yet.

import asyncio
import copy
import sqlite3

import pytest

from custom_components.smartcamper_suite.api import ApiClient, ProviderError, ServicePolicy
from custom_components.smartcamper_suite.auth import CredentialState, CredentialStore
from custom_components.smartcamper_suite.const import ModuleName
from custom_components.smartcamper_suite.fuel_stations import (
    FuelProviderRegistry,
    FuelStationsRuntime,
    ProviderResponse,
)
from custom_components.smartcamper_suite.migration import import_legacy_entry, preview_legacy_entry
from custom_components.smartcamper_suite.models import ValidationError, Vehicle
from custom_components.smartcamper_suite.modules import ModuleManager, ModuleRuntime
from custom_components.smartcamper_suite.providers import ProviderRegistry
from custom_components.smartcamper_suite.storage import SuiteStore


def test_vehicle_has_stable_id_and_validates_dimensions():
    vehicle = Vehicle.create("Carthago", length_m=7.65, width_m=2.34, height_m=3.2, weight_t=4.8, axle_count=2)
    assert vehicle.vehicle_id
    assert Vehicle.from_dict(vehicle.to_dict()).vehicle_id == vehicle.vehicle_id
    with pytest.raises(ValidationError):
        Vehicle.create("bad", length_m=0)


def test_store_round_trip_and_archive():
    store = SuiteStore()
    vehicle = Vehicle.create("Wohnmobil")
    store.save_vehicle(vehicle)
    assert len(store.list_vehicles()) == 1
    store.archive_vehicle(vehicle.vehicle_id)
    assert store.list_vehicles() == []
    assert len(store.list_vehicles(True)) == 1


def test_two_vehicles_share_provider_credentials_without_losing_identity(tmp_path):
    store = SuiteStore(tmp_path / "suite.sqlite")
    first = Vehicle.create("Carthago", tracker_entity_id="device_tracker.carthago")
    second = Vehicle.create("Knaus", tracker_entity_id="device_tracker.knaus")
    store.save_vehicle(first)
    store.save_vehicle(second)

    credentials = CredentialStore()
    credentials.put_api_key("global-petromap", "petromap", "synthetic-key")
    assert {item.vehicle_id for item in store.list_vehicles()} == {first.vehicle_id, second.vehicle_id}
    assert store.list_vehicles()[0].tracker_entity_id in {
        "device_tracker.carthago", "device_tracker.knaus"
    }
    credentials.put_api_key("global-petromap", "petromap", "replacement-key")
    assert credentials.get_secret("global-petromap") == "replacement-key"
    credentials.remove("global-petromap")
    assert credentials.get_secret("global-petromap") is None


def test_provider_registry_exposes_distinct_services_and_all_expected_providers():
    registry = ProviderRegistry()
    assert {provider.key for provider in registry.all()} == {
        "nakordoni", "tankerkoenig", "petromap", "carto", "geoapify", "nominatim"
    }
    assert registry.service("nakordoni", "routing").quota_key != registry.service("nakordoni", "border_forecast").quota_key
    assert registry.service("nominatim", "geocoding").requires_credentials is False


def test_store_rejects_malformed_sqlite_file_and_repeated_initialization(tmp_path):
    path = tmp_path / "broken.sqlite"
    path.write_text("not a sqlite database")
    with pytest.raises(sqlite3.DatabaseError):
        SuiteStore(path)

    healthy = SuiteStore(tmp_path / "healthy.sqlite")
    Vehicle.create("Persisted")
    healthy.close()
    reopened = SuiteStore(tmp_path / "healthy.sqlite")
    assert reopened.snapshot()["schema_version"] == 1
    reopened.close()


def test_shared_credentials_do_not_appear_in_public_status():
    credentials = CredentialStore()
    credentials.put_api_key("key-1", "petromap", "synthetic-secret")
    assert credentials.status("key-1")["state"] == CredentialState.VALID
    assert "synthetic-secret" not in str(credentials.status("key-1"))
    restored = CredentialStore()
    restored.load_api_keys(credentials.export_api_keys())
    assert restored.get_secret("key-1") == "synthetic-secret"
    assert "synthetic-secret" not in str(restored.records())


def test_modules_are_independent_and_disabled_by_default():
    manager = ModuleManager({ModuleName.ROUTE_PLANNER.value: True})
    asyncio.run(manager.async_setup(object()))
    assert manager.modules[ModuleName.ROUTE_PLANNER].started
    assert not manager.modules[ModuleName.FUEL_STATIONS].started
    asyncio.run(manager.async_unload())
    assert not manager.modules[ModuleName.ROUTE_PLANNER].started


def test_module_failure_isolated_from_other_enabled_modules():
    manager = ModuleManager({module.value: True for module in ModuleName})

    class FailingRuntime(ModuleRuntime):
        async def async_setup(self, _context):
            raise RuntimeError("synthetic module failure")

    manager.modules[ModuleName.FUEL_STATIONS] = FailingRuntime(ModuleName.FUEL_STATIONS, True)
    asyncio.run(manager.async_setup(object()))
    assert manager.modules[ModuleName.FUEL_STATIONS].error == "RuntimeError"
    assert manager.modules[ModuleName.ROUTE_PLANNER].started


def test_live_transport_is_blocked_without_injected_fake():
    async def run():
        with pytest.raises(ProviderError, match="live transport"):
            await ApiClient(policies={"x": ServicePolicy(timeout=1)}).request("x", "GET", "https://example.invalid")
    asyncio.run(run())


def test_oauth_refresh_is_single_flight_and_secret_free():
    async def run():
        credentials = CredentialStore()
        credentials.put_oauth("nkd", "nakordoni", "old-token", {"fuel.read"})
        calls = 0

        async def refresh(_old):
            nonlocal calls
            calls += 1
            await asyncio.sleep(0)
            return "new-token", "2099-01-01T00:00:00+00:00"

        result = await asyncio.gather(
            credentials.async_refresh_oauth("nkd", refresh),
            credentials.async_refresh_oauth("nkd", refresh),
        )
        assert result == ["new-token", "new-token"]
        assert calls == 1
        assert "new-token" not in str(credentials.status("nkd"))

    asyncio.run(run())


def test_fuel_provider_registry_and_two_vehicle_cache_isolation():
    async def run():
        requests = []

        async def transport(provider, url, params, headers):
            requests.append((provider, params.copy()))
            return ProviderResponse(200, {"ok": True, "stations": [{
                "id": f"{provider}-{params.get('lat')}", "name": "Station",
                "price": 1.7, "dist": 2.0, "lat": 50.0, "lng": 8.0,
                "isOpen": True, "street": "Main", "postCode": "12345", "place": "Town",
            }]})

        first = Vehicle.create("Wohnmobil", tracker_entity_id="device_tracker.womo", fuel_types=["diesel"], fuel_radius_km=20)
        second = Vehicle.create("Opel", tracker_entity_id="device_tracker.opel", fuel_types=["diesel"], fuel_radius_km=10)
        secrets = {"shared": "synthetic"}
        registry = FuelProviderRegistry(ProviderRegistry(), transport)
        runtime = FuelStationsRuntime(
            {first.vehicle_id: first, second.vehicle_id: second},
            {"tankerkoenig": {"credential_id": "shared"}}, registry, secrets.get,
        )
        first_result = await runtime.async_search(first.vehicle_id, 50.0, 8.0)
        second_result = await runtime.async_search(second.vehicle_id, 50.0, 8.0)
        assert first_result[0].provider == "tankerkoenig"
        assert second_result[0].provider == "tankerkoenig"
        assert len(requests) == 2
        assert requests[0][1]["rad"] != requests[1][1]["rad"]
        await runtime.async_unload()

    asyncio.run(run())


def test_legacy_preview_is_reversible_and_does_not_copy_secret():
    data = {"provider_mode": "tankerkoenig", "api_key": "synthetic-secret", "location_entity": "device_tracker.womo"}
    preview = preview_legacy_entry("legacy-1", data, {"fuel_type": "diesel", "radius": 20})
    assert preview.credential_fields == ("api_key",)
    assert "synthetic-secret" not in str(preview.as_dict())
    assert data["api_key"] == "synthetic-secret"


def test_legacy_import_is_opt_in_idempotent_and_rollback_safe():
    data = {
        "title": "Legacy Camper", "provider_mode": "tankerkoenig",
        "api_key": "synthetic-secret", "location_entity": "device_tracker.womo",
    }
    target = {}
    with pytest.raises(PermissionError):
        import_legacy_entry("legacy-1", data, target)
    result = import_legacy_entry("legacy-1", data, target, opt_in=True)
    assert result.imported is True
    assert len(target["vehicles"]) == 1
    assert "synthetic-secret" not in str(target)
    before_rollback = copy.deepcopy(target)
    result.transaction.rollback()
    assert target == {}
    target.update(before_rollback)
    repeated = import_legacy_entry("legacy-1", data, target, opt_in=True)
    assert repeated.already_imported is True

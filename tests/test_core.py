import asyncio
import sqlite3

import pytest

from custom_components.smartcamper_suite.api import ApiClient, ProviderError, ServicePolicy
from custom_components.smartcamper_suite.auth import CredentialState, CredentialStore
from custom_components.smartcamper_suite.const import ModuleName
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

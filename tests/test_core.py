import asyncio

import pytest

from custom_components.smartcamper_suite.api import ApiClient, ProviderError, ServicePolicy
from custom_components.smartcamper_suite.auth import CredentialState, CredentialStore
from custom_components.smartcamper_suite.const import ModuleName
from custom_components.smartcamper_suite.models import ValidationError, Vehicle
from custom_components.smartcamper_suite.modules import ModuleManager
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


def test_live_transport_is_blocked_without_injected_fake():
    async def run():
        with pytest.raises(ProviderError, match="live transport"):
            await ApiClient(policies={"x": ServicePolicy(timeout=1)}).request("x", "GET", "https://example.invalid")
    asyncio.run(run())

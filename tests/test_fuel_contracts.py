import asyncio

import pytest

from custom_components.smartcamper_suite.fuel_stations import (
    FuelConfigurationError,
    FuelProviderRegistry,
    FuelRateLimitError,
    FuelSearchQuery,
    FuelStationsRuntime,
    FuelUnavailableError,
    NakordoniAdapter,
    PetromapAdapter,
    ProviderResponse,
    TankerkoenigAdapter,
)
from custom_components.smartcamper_suite.models import Vehicle
from custom_components.smartcamper_suite.providers import ProviderRegistry


def query(fuel: str = "diesel") -> FuelSearchQuery:
    return FuelSearchQuery("vehicle-1", 50.0, 8.0, 20.0, fuel, 5)


def test_provider_capabilities_and_unsupported_fuels_are_explicit():
    async def run():
        async def transport(*_args):
            return ProviderResponse(200, {"ok": True, "stations": []})

        registry = FuelProviderRegistry(ProviderRegistry(), transport)
        assert registry.capability("tankerkoenig").fuels == frozenset({"diesel", "e5", "e10"})
        with pytest.raises(FuelConfigurationError):
            await PetromapAdapter(transport, PetromapAdapter.capability).async_search(query("hvo100"), "synthetic")
        with pytest.raises(FuelConfigurationError):
            await NakordoniAdapter(transport, NakordoniAdapter.capability).async_search(query("hvo100"), "synthetic")

    asyncio.run(run())


def test_petromap_and_nakordoni_contracts_normalize_price_and_address():
    async def run():
        calls = []

        async def transport(provider, url, params, headers):
            calls.append((provider, url, params, headers))
            if provider == "petromap":
                return ProviderResponse(200, {"places": [{
                    "kind": "fuel", "id": "p1", "name": "Petro", "street": "A", "postalCode": "1", "city": "B",
                    "location": {"lat": 50.1, "lon": 8.1}, "distanceM": 1200,
                    "network": {"name": "Brand"}, "fuel": {"price": {"amount": 1.8, "currency": "EUR"}},
                    "openNow": False,
                }]})
            return ProviderResponse(200, {"ok": True, "data": {"stations": [{
                "station_ref": "n1", "name": "Nako", "lat": 50.2, "lng": 8.2,
                "address": "C 2, D", "prices": {"diesel": {"price": 1.7}}, "is_open": True,
            }]}})
        registry = FuelProviderRegistry(ProviderRegistry(), transport)
        petro = await registry.adapter("petromap").async_search(query(), "synthetic")
        nako = await registry.adapter("nakordoni").async_search(query(), "synthetic")
        assert petro[0].price == 1.8 and petro[0].address == "A, 1 B"
        assert nako[0].price == 1.7 and nako[0].station_id == "n1"
        assert calls[0][3] == {"x-api-key": "synthetic"}
        assert calls[1][3] == {"Authorization": "Bearer synthetic"}

    asyncio.run(run())


def test_rate_limit_and_malformed_provider_responses_are_classified():
    async def run():
        async def limited(provider, *_args):
            return ProviderResponse(429, {"error": "rate_limited"})

        async def malformed(provider, *_args):
            return ProviderResponse(200, {"ok": True, "stations": {}})

        with pytest.raises(FuelRateLimitError):
            await TankerkoenigAdapter(limited, TankerkoenigAdapter.capability).async_search(query(), "synthetic")
        with pytest.raises(FuelUnavailableError):
            await TankerkoenigAdapter(malformed, TankerkoenigAdapter.capability).async_search(query(), "synthetic")

    asyncio.run(run())


def test_all_provider_payloads_empty_results_and_provider_specific_headers():
    async def run():
        calls = []

        async def transport(provider, url, params, headers):
            calls.append((provider, url, params, headers))
            if provider == "tankerkoenig":
                return ProviderResponse(200, {"ok": True, "stations": [{
                    "id": "tk-1", "name": "TK", "street": "Hauptstr.", "houseNumber": "1",
                    "postCode": "60311", "place": "Frankfurt", "lat": 50.11, "lng": 8.68,
                    "dist": 1.2, "price": 1.79, "isOpen": True,
                }]})
            if provider == "petromap":
                return ProviderResponse(200, {"places": []})
            return ProviderResponse(200, {"ok": True, "data": {"stations": [{
                "station_ref": "n-1", "name": "Nako", "distance_km": 2.0,
                "prices": {"lpg": {"price": 0.99}}, "is_open": True,
            }]}})

        registry = FuelProviderRegistry(ProviderRegistry(), transport)
        tanker = await registry.adapter("tankerkoenig").async_search(query("diesel"), "tk-secret")
        empty = await registry.adapter("petromap").async_search(query("diesel"), "pm-secret")
        nako = await registry.adapter("nakordoni").async_search(query("lpg"), "nako-secret")

        assert tanker[0].station_id == "tk-1"
        assert tanker[0].address == "Hauptstr. 1, 60311 Frankfurt"
        assert empty == []
        assert nako[0].fuel_type == "lpg"
        assert calls[0][3] == {"Authorization": "Bearer tk-secret"}
        assert calls[1][3] == {"x-api-key": "pm-secret"}
        assert calls[2][3] == {"Authorization": "Bearer nako-secret"}

    asyncio.run(run())


def test_auth_and_timeout_errors_fall_back_to_next_selected_provider():
    async def run():
        calls = []

        async def transport(provider, *_args):
            calls.append(provider)
            if provider == "tankerkoenig":
                return ProviderResponse(401, {"error": "invalid"})
            if provider == "petromap":
                raise TimeoutError
            return ProviderResponse(200, {"ok": True, "data": {"stations": [{
                "station_ref": "n-2", "name": "Fallback", "prices": {"diesel": {"price": 1.75}},
            }]}})

        vehicle = Vehicle.create("Womo", fuel_types=["diesel"], fuel_provider_modes=["tankerkoenig", "petromap", "nakordoni"])
        registry = FuelProviderRegistry(ProviderRegistry(), transport)
        runtime = FuelStationsRuntime(
            {vehicle.vehicle_id: vehicle},
            {provider: {"credential_id": provider} for provider in ("tankerkoenig", "petromap", "nakordoni")},
            registry,
            {provider: f"synthetic-{provider}" for provider in ("tankerkoenig", "petromap", "nakordoni")}.get,
        )

        stations = await runtime.async_search(vehicle.vehicle_id, 50.0, 8.0)
        assert stations[0].provider == "nakordoni"
        assert calls[:2] == ["tankerkoenig", "petromap"]
        assert calls[2:] == ["nakordoni", "nakordoni"]  # usage check plus station search
        await runtime.async_unload()

    asyncio.run(run())


def test_two_vehicles_share_one_provider_account_and_cache_without_duplicate_searches():
    async def run():
        search_calls = 0
        usage_calls = 0

        async def transport(_provider, url, _params, _headers):
            nonlocal search_calls, usage_calls
            if "account/usage" in url:
                usage_calls += 1
                await asyncio.sleep(0)
                return ProviderResponse(200, {"ok": True, "data": {"quotas": {"cheap": {"remaining": 8}}}})
            search_calls += 1
            await asyncio.sleep(0)
            return ProviderResponse(200, {"ok": True, "data": {"stations": [{
                "station_ref": "shared", "name": "Shared", "distance_km": 1.0,
                "prices": {"diesel": {"price": 1.70}},
            }]}})

        first = Vehicle.create("Wohnmobil", tracker_entity_id="device_tracker.womo", fuel_types=["diesel"], extra={"country_code": "DE"})
        second = Vehicle.create("Opel", tracker_entity_id="device_tracker.opel", fuel_types=["diesel"], extra={"country_code": "DE"})
        registry = FuelProviderRegistry(ProviderRegistry(), transport)
        runtime = FuelStationsRuntime(
            {first.vehicle_id: first, second.vehicle_id: second},
            {"nakordoni": {"credential_id": "shared", "markets_allowed": ["DE"]}},
            registry,
            {"shared": "synthetic-token"}.get,
        )

        results = await asyncio.gather(
            runtime.async_search(first.vehicle_id, 50.0, 8.0),
            runtime.async_search(second.vehicle_id, 50.0, 8.0),
        )
        assert [items[0].station_id for items in results] == ["shared", "shared"]
        assert search_calls == 1
        assert usage_calls == 1
        await runtime.async_unload()

    asyncio.run(run())


def test_fallback_uses_second_active_provider_without_reusing_first_error():
    async def run():
        calls = []

        async def transport(provider, _url, _params, _headers):
            calls.append(provider)
            if provider == "tankerkoenig":
                return ProviderResponse(503, {})
            return ProviderResponse(200, {"places": [{
                "id": "p1", "name": "Fallback", "location": {"lat": 50.0, "lon": 8.0},
                "distanceM": 1000, "fuel": {"price": {"amount": 1.9}},
            }]})

        vehicle = Vehicle.create("Womo", fuel_types=["diesel"], fuel_provider_modes=["tankerkoenig", "petromap"])
        registry = FuelProviderRegistry(ProviderRegistry(), transport)
        runtime = FuelStationsRuntime(
            {vehicle.vehicle_id: vehicle},
            {"tankerkoenig": {"credential_id": "tk"}, "petromap": {"credential_id": "pm"}},
            registry, {"tk": "synthetic-tk", "pm": "synthetic-pm"}.get,
        )
        stations = await runtime.async_search(vehicle.vehicle_id, 50.0, 8.0)
        assert stations[0].provider == "petromap"
        assert calls == ["tankerkoenig", "petromap"]

    asyncio.run(run())


def test_shared_account_deduplicates_concurrent_requests_and_respects_market_policy():
    async def run():
        calls = 0

        async def transport(provider, _url, _params, _headers):
            nonlocal calls
            calls += 1
            await asyncio.sleep(0)
            if "account/usage" in _url:
                return ProviderResponse(200, {"ok": True, "data": {"quotas": {"cheap": {"limit": 10, "used": 1, "remaining": 9}}, "markets": {"approved": ["DE"], "available": ["DE"]}}})
            return ProviderResponse(200, {"ok": True, "data": {"stations": [{
                "station_ref": "n1", "name": "Nako", "distance_km": 1.0,
                "prices": {"diesel": {"price": 1.7}},
            }]}})

        vehicle = Vehicle.create("Womo", fuel_types=["diesel"], fuel_provider_modes=["auto"], extra={"country_code": "DE"})
        registry = FuelProviderRegistry(ProviderRegistry(), transport)
        runtime = FuelStationsRuntime(
            {vehicle.vehicle_id: vehicle},
            {"nakordoni": {"credential_id": "nkd", "markets_allowed": ["DE"]}},
            registry, {"nkd": "synthetic"}.get,
        )
        first, second = await asyncio.gather(
            runtime.async_search(vehicle.vehicle_id, 50.0, 8.0),
            runtime.async_search(vehicle.vehicle_id, 50.0, 8.0),
        )
        assert first[0].station_id == second[0].station_id == "n1"
        assert calls == 2
        assert runtime.provider_usage["nkd"].cheap_remaining == 9
        await runtime.async_unload()

    asyncio.run(run())


def test_refresh_modes_ignore_small_tracker_jitter_and_allow_manual_mode():
    vehicle = Vehicle.create(
        "Womo",
        tracker_entity_id="device_tracker.womo",
        fuel_refresh_mode="movement",
        fuel_display_options={"movement_threshold_km": 0.5},
    )
    old = type("State", (), {"entity_id": vehicle.tracker_entity_id, "attributes": {"latitude": 50.0, "longitude": 8.0}})()
    small = type("State", (), {"entity_id": vehicle.tracker_entity_id, "attributes": {"latitude": 50.0001, "longitude": 8.0001}})()
    large = type("State", (), {"entity_id": vehicle.tracker_entity_id, "attributes": {"latitude": 50.01, "longitude": 8.01}})()
    assert not FuelStationsRuntime._location_changed(old, small, vehicle)
    assert FuelStationsRuntime._location_changed(old, large, vehicle)
    assert FuelStationsRuntime._location_changed(old, None, vehicle)

    runtime = FuelStationsRuntime({}, {}, FuelProviderRegistry(ProviderRegistry(), lambda *_args: None), {}.get)
    asyncio.run(runtime.async_start_background(object(), enabled=False))
    assert runtime._remove_listeners == []
    asyncio.run(runtime.async_unload())

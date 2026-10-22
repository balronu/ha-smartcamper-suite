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

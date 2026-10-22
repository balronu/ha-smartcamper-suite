import asyncio

import pytest

from custom_components.smartcamper_suite.models import Vehicle
from custom_components.smartcamper_suite.route_planner import (
    NakordoniMotorhomeProvider,
    RouteCoordinator,
    RouteError,
    RoutePlannerRuntime,
    RouteRequest,
    Waypoint,
    build_nakordoni_parameters,
    export_gpx,
)


def vehicle(**kwargs):
    values = {"vehicle_type": "motorhome", "length_m": 7.65, "width_m": 2.34, "height_m": 3.2, "weight_t": 4.8, "axle_count": 2}
    values.update(kwargs)
    return Vehicle.create("Wohnmobil", **values)


def request(vehicle_id):
    return RouteRequest(vehicle_id, Waypoint(50, 8), Waypoint(51, 9), (Waypoint(50.5, 8.5, "Via"),))


def fixture():
    return {"ok": True, "data": {"route": {
        "distance_m": 123456, "duration_s": 7200,
        "geometry": [[50, 8], [50.5, 8.5], [51, 9]],
        "warnings": [{"code": "switzerland_restriction", "message": "Schweizer Restriktionen prüfen"}],
        "tolls": {"status": "estimated", "estimate": True},
        "countries": ["DE", "CH"], "restriction_hits": ["over_3_5t"],
    }}}


def test_parameters_use_central_vehicle_profile_and_no_driver_time_fields():
    profile = vehicle()
    params = build_nakordoni_parameters(request("v1"), profile)
    assert params["vehicle_type"] == "motorhome"
    assert params["weight"] == 4.8
    assert params["via"] == "50.5,8.5"
    assert "crew" not in params


def test_missing_dimensions_are_rejected_without_defaults():
    with pytest.raises(RouteError, match="Länge"):
        build_nakordoni_parameters(request("v1"), vehicle(height_m=None))


def test_provider_normalizes_beta_warnings_tolls_and_restrictions():
    provider = NakordoniMotorhomeProvider("synthetic")
    async def run():
        provider.transport = lambda _params: asyncio.sleep(0, result=fixture())
        return await provider.calculate(request("v1"), vehicle())
    result = asyncio.run(run())
    assert result.synthetic is False
    assert result.metadata["tolls"]["estimate"] is True
    assert "switzerland_restriction" in {item.code for item in result.warnings}
    assert "motorhome_beta" in {item.code for item in result.warnings}


def test_coordinator_deduplicates_concurrent_requests_and_cache_hits():
    calls = 0
    async def run():
        nonlocal calls
        provider = NakordoniMotorhomeProvider("synthetic")
        async def transport(_params):
            nonlocal calls
            calls += 1
            await asyncio.sleep(0.01)
            return fixture()
        provider.transport = transport
        coordinator = RouteCoordinator(provider, daily_limit=1)
        profile = vehicle()
        first, second = await asyncio.gather(
            coordinator.async_calculate(request("v1"), profile),
            coordinator.async_calculate(request("v1"), profile),
        )
        cached = await coordinator.async_calculate(request("v1"), profile)
        assert first == second == cached
        assert calls == 1
        assert coordinator.used == 1
    asyncio.run(run())


def test_quota_is_shared_at_coordinator_level():
    async def run():
        provider = NakordoniMotorhomeProvider("synthetic", lambda _params: asyncio.sleep(0, result=fixture()))
        coordinator = RouteCoordinator(provider, daily_limit=1)
        profile = vehicle()
        await coordinator.async_calculate(request("v1"), profile)
        with pytest.raises(RouteError, match="kontingent"):
            await coordinator.async_calculate(request("v2"), profile)
    asyncio.run(run())


def test_runtime_does_not_start_live_routing_without_explicit_transport():
    async def run():
        profile = vehicle()
        runtime = RoutePlannerRuntime({profile.vehicle_id: profile}, "synthetic")
        with pytest.raises(RouteError, match="nicht live aktiviert"):
            await runtime.async_calculate({"vehicle_id": profile.vehicle_id, "origin": {"latitude": 50, "longitude": 8}, "destination": {"latitude": 51, "longitude": 9}})
    asyncio.run(run())


def test_gpx_export_is_offline_and_supports_route_track_combined():
    route = {
        "name": "Schweiz & <Test>", "origin": {"latitude": 50, "longitude": 8},
        "waypoints": [{"latitude": 50.5, "longitude": 8.5}],
        "destination": {"latitude": 51, "longitude": 9},
        "geometry": [{"latitude": 50, "longitude": 8}, {"latitude": 51, "longitude": 9}],
    }
    xml = export_gpx(route)
    assert b"<rte>" in xml and b"<trk>" in xml
    assert b"Schweiz" in xml  # unsafe filename characters are sanitized

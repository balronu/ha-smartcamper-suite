from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SuiteRuntime
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    runtime: SuiteRuntime = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [FuelStationsSensor(runtime, vehicle_id) for vehicle_id in runtime.fuel.vehicles]
        + [RoutePlannerSensor(runtime, vehicle_id) for vehicle_id in runtime.route.vehicles]
    )


class FuelStationsSensor(SensorEntity):
    """One entity per vehicle; station details stay in attributes."""

    _attr_should_poll = False
    _attr_native_unit_of_measurement = "stations"

    def __init__(self, runtime: SuiteRuntime, vehicle_id: str) -> None:
        self._runtime = runtime
        self._vehicle_id = vehicle_id
        vehicle = runtime.fuel.vehicles[vehicle_id]
        self._attr_name = f"{vehicle.name} Tankstellen"
        self._attr_unique_id = f"{vehicle_id}_fuel_stations"
        self._attr_extra_state_attributes = {}

    @property
    def native_value(self) -> int:
        stations = self._runtime.fuel.results.get((self._vehicle_id, "all"), [])
        return len(stations)

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        stations = self._runtime.fuel.results.get((self._vehicle_id, "all"), [])
        station_data: dict[str, dict[str, object]] = {}
        for station in stations:
            item = station_data.setdefault(station.station_id, {
                "station_id": station.station_id,
                "name": station.name,
                "distance_km": station.distance_km,
                "address": station.address,
                "is_open": station.is_open,
                "provider": station.provider,
                "brand": station.brand,
                "latitude": station.latitude,
                "longitude": station.longitude,
                "fuel_prices": {},
            })
            prices = item["fuel_prices"]
            if isinstance(prices, dict):
                prices[station.fuel_type] = station.price
        provider_usage = {
            provider: {
                "quotas": usage.quotas,
                "markets_approved": list(usage.markets_approved),
                "markets_available": list(usage.markets_available),
                "checked_at": usage.checked_at,
            }
            for provider, account in self._runtime.fuel.accounts.items()
            if account.get("credential_id") in self._runtime.fuel.provider_usage
            for usage in [self._runtime.fuel.provider_usage[account["credential_id"]]]
        }
        return {
            "vehicle_id": self._vehicle_id,
            "fuel_types": list(self._runtime.fuel.vehicles[self._vehicle_id].fuel_types or ["diesel"]),
            "radius_km": self._runtime.fuel.vehicles[self._vehicle_id].fuel_radius_km,
            "station_count": self._runtime.fuel.vehicles[self._vehicle_id].fuel_station_count,
            "fetch_mode": self._runtime.fuel.vehicles[self._vehicle_id].fuel_refresh_mode,
            **self._runtime.fuel.status.get(self._vehicle_id, {"state": "idle"}),
            "stations": list(station_data.values()),
            "provider_usage": provider_usage,
        }

    async def async_update(self) -> None:
        vehicle = self._runtime.fuel.vehicles.get(self._vehicle_id)
        if vehicle is None or vehicle.archived or vehicle.tracker_entity_id is None:
            return
        state = self.hass.states.get(vehicle.tracker_entity_id)
        if state is None or state.state in {"unknown", "unavailable"}:
            return
        try:
            latitude = float(state.attributes["latitude"])
            longitude = float(state.attributes["longitude"])
        except (KeyError, TypeError, ValueError):
            return
        await self._runtime.fuel.async_search(self._vehicle_id, latitude, longitude)
        self.async_write_ha_state()


class RoutePlannerSensor(SensorEntity):
    """Expose the last explicit route without starting background work."""

    _attr_should_poll = False
    _attr_native_unit_of_measurement = "km"

    def __init__(self, runtime: SuiteRuntime, vehicle_id: str) -> None:
        self._runtime = runtime
        self._vehicle_id = vehicle_id
        self._attr_name = f"{runtime.route.vehicles[vehicle_id].name} Route"
        self._attr_unique_id = f"{vehicle_id}_route_planner"

    @property
    def native_value(self) -> float | None:
        result = self._runtime.route.results.get(self._vehicle_id)
        return round(result.distance_m / 1000, 1) if result else None

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        result = self._runtime.route.results.get(self._vehicle_id)
        if result is None:
            return {"vehicle_id": self._vehicle_id, "state": "idle", "warnings": []}
        return {
            "vehicle_id": self._vehicle_id,
            "state": "ready",
            "provider": result.provider,
            "duration_s": result.duration_s,
            "geometry": [point.as_dict() for point in result.geometry],
            "warnings": [warning.message for warning in result.warnings],
            "metadata": result.metadata,
            "beta": bool(result.metadata.get("beta")),
        }

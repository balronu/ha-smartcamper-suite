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
        FuelStationsSensor(runtime, vehicle_id)
        for vehicle_id in runtime.fuel.vehicles
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
        return {
            "vehicle_id": self._vehicle_id,
            "stations": [
                {
                    "station_id": station.station_id,
                    "name": station.name,
                    "price": station.price,
                    "distance_km": station.distance_km,
                    "address": station.address,
                    "is_open": station.is_open,
                    "provider": station.provider,
                    "fuel_type": station.fuel_type,
                    "brand": station.brand,
                    "latitude": station.latitude,
                    "longitude": station.longitude,
                }
                for station in stations
            ],
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


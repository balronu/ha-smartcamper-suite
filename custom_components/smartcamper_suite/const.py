from __future__ import annotations

from enum import StrEnum

DOMAIN = "smartcamper_suite"
STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}.storage"
CONF_VEHICLES = "vehicles"
CONF_PROVIDERS = "providers"
CONF_MODULES = "modules"


class ModuleName(StrEnum):
    TRAVEL_JOURNAL = "travel_journal"
    FUEL_STATIONS = "fuel_stations"
    ROUTE_PLANNER = "route_planner"
    BORDER_FORECAST = "border_forecast"


DEFAULT_MODULES = {module.value: False for module in ModuleName}

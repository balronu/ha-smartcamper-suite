from __future__ import annotations

from enum import StrEnum

DOMAIN = "smartcamper_suite"
VERSION = "0.3.0-beta.2"
STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}.storage"
CONF_VEHICLES = "vehicles"
CONF_PROVIDERS = "providers"
CONF_MODULES = "modules"
NAKORDONI_OAUTH_IMPLEMENTATION = "nakordoni"
NAKORDONI_OAUTH_CLIENT_ID = "nkd_30ad5daeb089abfc3c1ea20b"
NAKORDONI_OAUTH_AUTHORIZE_URL = "https://api.nakordoni.dev/oauth/authorize"
NAKORDONI_OAUTH_TOKEN_URL = "https://api.nakordoni.dev/oauth/token"
CONF_NAKORDONI_AUTH_METHOD = "nakordoni_auth_method"


class ModuleName(StrEnum):
    TRAVEL_JOURNAL = "travel_journal"
    FUEL_STATIONS = "fuel_stations"
    ROUTE_PLANNER = "route_planner"
    BORDER_FORECAST = "border_forecast"


DEFAULT_MODULES = {module.value: False for module in ModuleName}

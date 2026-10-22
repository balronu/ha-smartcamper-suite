from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import voluptuous as vol

try:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
except ImportError:  # Allows domain-layer tests without Home Assistant installed.
    ConfigEntry = object  # type: ignore[assignment,misc]
    HomeAssistant = object  # type: ignore[assignment,misc]

from .api import ApiClient
from .auth import CredentialStore
from .const import CONF_NAKORDONI_AUTH_METHOD, DOMAIN, ModuleName
from .frontend import async_register_frontend, async_unregister_frontend
from .fuel_stations import FuelProviderRegistry, FuelStationsRuntime, ProviderResponse
from .models import Vehicle
from .modules import ModuleManager
from .oauth2 import async_register as async_register_oauth
from .providers import ProviderRegistry
from .storage import SuiteStore

PLATFORMS: list[str] = ["sensor"]
SERVICE_SET_CREDENTIAL = "set_credential"
SERVICE_REMOVE_CREDENTIAL = "remove_credential"
SERVICE_REFRESH_FUEL = "refresh_fuel_stations"
_CREDENTIAL_SCHEMA = vol.Schema({
    vol.Required("entry_id"): str,
    vol.Required("credential_id"): str,
    vol.Required("provider"): vol.In(("tankerkoenig", "petromap", "nakordoni")),
    vol.Required("api_key"): str,
})
_REMOVE_CREDENTIAL_SCHEMA = vol.Schema({
    vol.Required("entry_id"): str,
    vol.Required("credential_id"): str,
})
_REFRESH_FUEL_SCHEMA = vol.Schema({vol.Required("vehicle_id"): str})


@dataclass(slots=True)
class SuiteRuntime:
    providers: ProviderRegistry
    credentials: CredentialStore
    api: ApiClient
    modules: ModuleManager
    store: SuiteStore
    fuel: FuelStationsRuntime


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    await async_register_frontend(hass)
    domain_data = hass.data.setdefault(DOMAIN, {})
    if not domain_data.get("oauth_registered"):
        async_register_oauth(hass)
        domain_data["oauth_registered"] = True
    store = await hass.async_add_executor_job(
        SuiteStore, hass.config.path(".storage", "smartcamper_suite.sqlite")
    )
    providers = ProviderRegistry()
    credentials = CredentialStore()
    credentials.load_api_keys(entry.data.get("credentials"))
    oauth_session = None
    if isinstance(entry.data.get("token"), dict) and entry.data.get("auth_implementation") == "nakordoni" and entry.data.get(CONF_NAKORDONI_AUTH_METHOD) == "oauth2":
        from homeassistant.helpers.config_entry_oauth2_flow import (
            OAuth2Session,
            async_get_config_entry_implementation,
        )

        implementation = await async_get_config_entry_implementation(hass, entry)
        oauth_session = OAuth2Session(hass, entry, implementation)
        token = entry.data["token"].get("access_token")
        if isinstance(token, str) and token:
            credentials.put_oauth("nakordoni-oauth", "nakordoni", token, set(), entry.data["token"].get("expires_at"), entry.data["token"].get("refresh_token"))

    async def transport(provider: str, url: str, params: dict[str, str], headers: dict[str, str]) -> ProviderResponse:
        """Perform one provider request through HA's shared aiohttp session."""
        from homeassistant.helpers.aiohttp_client import async_get_clientsession

        session = async_get_clientsession(hass)
        request_headers = dict(headers)
        if provider == "nakordoni" and oauth_session is not None:
            response = await oauth_session.async_request("GET", url, params=params, timeout=15)
            try:
                return ProviderResponse(response.status, await response.json(content_type=None), dict(response.headers))
            finally:
                response.release()
        async with session.get(url, params=params, headers=request_headers, timeout=15) as response:
            return ProviderResponse(response.status, await response.json(content_type=None), dict(response.headers))

    vehicles = {}
    for raw_vehicle in entry.options.get("vehicles", []):
        try:
            vehicle = Vehicle.from_dict(raw_vehicle)
        except (TypeError, ValueError, KeyError):
            continue
        vehicles[vehicle.vehicle_id] = vehicle
    provider_accounts = dict(entry.options.get("provider_accounts", {}))
    if oauth_session is not None:
        token_data = entry.data["token"]
        provider_accounts.setdefault("nakordoni", {
            "credential_id": "nakordoni-oauth",
            **{
                key: token_data[key]
                for key in ("markets_approved", "markets_granted", "markets_available", "markets_allowed")
                if isinstance(token_data.get(key), (list, tuple, set))
            },
        })
    fuel = FuelStationsRuntime(
        vehicles,
        provider_accounts,
        FuelProviderRegistry(providers, transport),
        credentials.get_secret,
    )
    runtime = SuiteRuntime(
        providers, credentials, ApiClient(), ModuleManager(entry.options.get("modules")), store, fuel
    )
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = runtime
    if hasattr(hass, "services") and not hass.services.has_service(DOMAIN, SERVICE_SET_CREDENTIAL):
        hass.services.async_register(DOMAIN, SERVICE_SET_CREDENTIAL, _async_set_credential, _CREDENTIAL_SCHEMA)
        hass.services.async_register(DOMAIN, SERVICE_REMOVE_CREDENTIAL, _async_remove_credential, _REMOVE_CREDENTIAL_SCHEMA)
        hass.services.async_register(DOMAIN, SERVICE_REFRESH_FUEL, _async_refresh_fuel, _REFRESH_FUEL_SCHEMA)
    await runtime.modules.async_setup(runtime)
    await runtime.fuel.async_start_background(
        hass,
        runtime.modules.modules[ModuleName.FUEL_STATIONS].started,
    )
    return True


async def _async_set_credential(call: Any) -> None:
    runtime: SuiteRuntime = call.hass.data[DOMAIN][call.data["entry_id"]]
    runtime.credentials.replace_api_key(
        call.data["credential_id"], call.data["provider"], call.data["api_key"]
    )
    runtime.fuel.accounts.setdefault(call.data["provider"], {})["credential_id"] = call.data["credential_id"]
    entry = call.hass.config_entries.async_get_entry(call.data["entry_id"])
    if entry is not None:
        call.hass.config_entries.async_update_entry(
            entry, data={**entry.data, "credentials": runtime.credentials.export_api_keys()}
        )


async def _async_remove_credential(call: Any) -> None:
    runtime: SuiteRuntime = call.hass.data[DOMAIN][call.data["entry_id"]]
    runtime.credentials.remove(call.data["credential_id"])
    entry = call.hass.config_entries.async_get_entry(call.data["entry_id"])
    if entry is not None:
        call.hass.config_entries.async_update_entry(
            entry, data={**entry.data, "credentials": runtime.credentials.export_api_keys()}
        )


async def _async_refresh_fuel(call: Any) -> None:
    """Refresh one vehicle from its configured tracker without duplicating credentials."""
    runtime = next(
        (value for key, value in call.hass.data[DOMAIN].items() if key != "_frontend" and isinstance(value, SuiteRuntime)),
        None,
    )
    if runtime is None:
        return
    vehicle = runtime.fuel.vehicles.get(call.data["vehicle_id"])
    if vehicle is None or vehicle.tracker_entity_id is None:
        return
    state = call.hass.states.get(vehicle.tracker_entity_id)
    if state is None:
        return
    try:
        latitude = float(state.attributes["latitude"])
        longitude = float(state.attributes["longitude"])
    except (KeyError, TypeError, ValueError):
        return
    await runtime.fuel.async_search(vehicle.vehicle_id, latitude, longitude)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    runtime: SuiteRuntime = hass.data[DOMAIN].pop(entry.entry_id)
    await runtime.fuel.async_unload()
    await runtime.modules.async_unload()
    await hass.async_add_executor_job(runtime.store.close)
    if not any(key != "_frontend" for key in hass.data[DOMAIN]):
        await async_unregister_frontend(hass)
    return True

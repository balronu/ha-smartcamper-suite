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
from .const import DOMAIN
from .frontend import async_register_frontend, async_unregister_frontend
from .fuel_stations import FuelProviderRegistry, FuelStationsRuntime, ProviderResponse
from .modules import ModuleManager
from .providers import ProviderRegistry
from .storage import SuiteStore

PLATFORMS: list[str] = ["sensor"]
SERVICE_SET_CREDENTIAL = "set_credential"
SERVICE_REMOVE_CREDENTIAL = "remove_credential"
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
    store = await hass.async_add_executor_job(
        SuiteStore, hass.config.path(".storage", "smartcamper_suite.sqlite")
    )
    providers = ProviderRegistry()
    credentials = CredentialStore()
    credentials.load_api_keys(entry.data.get("credentials"))

    async def transport(provider: str, url: str, params: dict[str, str], headers: dict[str, str]) -> ProviderResponse:
        """Perform one provider request through HA's shared aiohttp session."""
        from homeassistant.helpers.aiohttp_client import async_get_clientsession

        session = async_get_clientsession(hass)
        request_headers = dict(headers)
        async with session.get(url, params=params, headers=request_headers, timeout=15) as response:
            return ProviderResponse(response.status, await response.json(content_type=None), dict(response.headers))

    vehicles = {}
    for raw_vehicle in entry.options.get("vehicles", []):
        try:
            from .models import Vehicle
            vehicle = Vehicle.from_dict(raw_vehicle)
        except (TypeError, ValueError, KeyError):
            continue
        vehicles[vehicle.vehicle_id] = vehicle
    fuel = FuelStationsRuntime(
        vehicles,
        entry.options.get("provider_accounts", {}),
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
    await runtime.modules.async_setup(runtime)
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


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    runtime: SuiteRuntime = hass.data[DOMAIN].pop(entry.entry_id)
    await runtime.fuel.async_unload()
    await runtime.modules.async_unload()
    await hass.async_add_executor_job(runtime.store.close)
    if not any(key != "_frontend" for key in hass.data[DOMAIN]):
        await async_unregister_frontend(hass)
    return True

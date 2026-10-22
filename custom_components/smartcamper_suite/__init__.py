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
from .journal import JournalRuntime, JournalStore, JournalVehicle
from .models import Vehicle
from .modules import ModuleManager
from .oauth2 import async_register as async_register_oauth
from .providers import ProviderRegistry
from .route_planner import ROUTE_ENDPOINT, RoutePlannerRuntime
from .storage import SuiteStore

PLATFORMS: list[str] = ["sensor"]
SERVICE_SET_CREDENTIAL = "set_credential"
SERVICE_REMOVE_CREDENTIAL = "remove_credential"
SERVICE_REFRESH_FUEL = "refresh_fuel_stations"
SERVICE_CALCULATE_ROUTE = "calculate_route"
SERVICE_JOURNAL_CREATE_TRIP = "journal_create_trip"
SERVICE_JOURNAL_UPDATE_TRIP = "journal_update_trip"
SERVICE_JOURNAL_DELETE_TRIP = "journal_delete_trip"
SERVICE_JOURNAL_CREATE_STAY = "journal_create_stay"
SERVICE_JOURNAL_CREATE_STOP = "journal_create_stop"
SERVICE_JOURNAL_CREATE_EXPENSE = "journal_create_expense"
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
_ROUTE_SCHEMA = vol.Schema({
    vol.Required("vehicle_id"): str,
    vol.Required("origin"): dict,
    vol.Required("destination"): dict,
    vol.Optional("via", default=[]): [dict],
    vol.Optional("alternatives", default=0): vol.All(int, vol.Range(min=0, max=2)),
    vol.Optional("traffic", default="off"): vol.In(("off", "forecast", "live")),
})
_JOURNAL_TRIP_SCHEMA = vol.Schema({
    vol.Optional("entry_id"): str,
    vol.Required("vehicle_id"): str,
    vol.Required("title"): str,
    vol.Optional("description", default=""): str,
    vol.Optional("destination", default=""): str,
    vol.Optional("status", default="planned"): vol.In(("planned", "active", "completed", "cancelled")),
})
_JOURNAL_ID_SCHEMA = vol.Schema({vol.Optional("entry_id"): str, vol.Required("vehicle_id"): str, vol.Required("trip_id"): str})
_JOURNAL_ITEM_SCHEMA = vol.Schema({
    vol.Optional("entry_id"): str,
    vol.Required("vehicle_id"): str,
    vol.Optional("trip_id"): str,
    vol.Optional("name", default=""): str,
    vol.Optional("category", default="other"): str,
    vol.Optional("amount_minor", default=0): int,
    vol.Optional("currency", default="EUR"): str,
    vol.Optional("note", default=""): str,
})


@dataclass(slots=True)
class SuiteRuntime:
    providers: ProviderRegistry
    credentials: CredentialStore
    api: ApiClient
    modules: ModuleManager
    store: SuiteStore
    fuel: FuelStationsRuntime
    route: RoutePlannerRuntime
    journal: JournalRuntime


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    await async_register_frontend(hass)
    from .journal_api import async_register as async_register_journal_api
    async_register_journal_api(hass)
    domain_data = hass.data.setdefault(DOMAIN, {})
    if not domain_data.get("oauth_registered"):
        async_register_oauth(hass)
        domain_data["oauth_registered"] = True
    store = await hass.async_add_executor_job(
        SuiteStore, hass.config.path(".storage", "smartcamper_suite.sqlite")
    )
    journal_store = await hass.async_add_executor_job(
        JournalStore, hass.config.path(".storage", "smartcamper_suite_travel_journal.sqlite")
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
    nakordoni_credential = None
    account = provider_accounts.get("nakordoni")
    if isinstance(account, dict):
        credential_id = account.get("credential_id")
        if isinstance(credential_id, str):
            nakordoni_credential = credentials.get_secret(credential_id)
    async def route_transport(parameters: dict[str, Any]) -> dict[str, Any]:
        """Use the suite-owned HA transport only for an explicit route action."""
        response = await transport(
            "nakordoni", ROUTE_ENDPOINT,
            {key: str(value) for key, value in parameters.items() if value != ""},
            {"Authorization": f"Bearer {nakordoni_credential}"} if nakordoni_credential else {},
        )
        payload = response.payload
        if not isinstance(payload, dict):
            raise TypeError("Nakordoni returned a non-object response")
        return {**payload, "status": response.status, "headers": response.headers}

    route = RoutePlannerRuntime(vehicles, nakordoni_credential, route_transport)
    journal_vehicles = {
        vehicle_id: JournalVehicle(vehicle_id, vehicle.name, vehicle.tracker_entity_id)
        for vehicle_id, vehicle in vehicles.items()
    }
    journal = JournalRuntime(
        journal_store,
        journal_vehicles,
        bool(entry.options.get("modules", {}).get(ModuleName.TRAVEL_JOURNAL.value, False)),
    )
    runtime = SuiteRuntime(
        providers, credentials, ApiClient(), ModuleManager(entry.options.get("modules")), store, fuel, route, journal
    )
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = runtime
    if hasattr(hass, "services") and not hass.services.has_service(DOMAIN, SERVICE_SET_CREDENTIAL):
        hass.services.async_register(DOMAIN, SERVICE_SET_CREDENTIAL, _async_set_credential, _CREDENTIAL_SCHEMA)
        hass.services.async_register(DOMAIN, SERVICE_REMOVE_CREDENTIAL, _async_remove_credential, _REMOVE_CREDENTIAL_SCHEMA)
        hass.services.async_register(DOMAIN, SERVICE_REFRESH_FUEL, _async_refresh_fuel, _REFRESH_FUEL_SCHEMA)
        hass.services.async_register(DOMAIN, SERVICE_CALCULATE_ROUTE, _async_calculate_route, _ROUTE_SCHEMA)
        hass.services.async_register(DOMAIN, SERVICE_JOURNAL_CREATE_TRIP, _async_journal_create_trip, _JOURNAL_TRIP_SCHEMA)
        hass.services.async_register(DOMAIN, SERVICE_JOURNAL_UPDATE_TRIP, _async_journal_update_trip, _JOURNAL_ID_SCHEMA.extend({vol.Optional("title"): str, vol.Optional("description"): str, vol.Optional("destination"): str, vol.Optional("status"): str}))
        hass.services.async_register(DOMAIN, SERVICE_JOURNAL_DELETE_TRIP, _async_journal_delete_trip, _JOURNAL_ID_SCHEMA)
        hass.services.async_register(DOMAIN, SERVICE_JOURNAL_CREATE_STAY, _async_journal_create_stay, _JOURNAL_ITEM_SCHEMA)
        hass.services.async_register(DOMAIN, SERVICE_JOURNAL_CREATE_STOP, _async_journal_create_stop, _JOURNAL_ITEM_SCHEMA)
        hass.services.async_register(DOMAIN, SERVICE_JOURNAL_CREATE_EXPENSE, _async_journal_create_expense, _JOURNAL_ITEM_SCHEMA)
    await runtime.modules.async_setup(runtime)
    await runtime.journal.async_start(hass)
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
    if call.data["provider"] == "nakordoni":
        runtime.route.coordinator.provider.credential = runtime.credentials.get_secret(call.data["credential_id"])
    entry = call.hass.config_entries.async_get_entry(call.data["entry_id"])
    if entry is not None:
        call.hass.config_entries.async_update_entry(
            entry, data={**entry.data, "credentials": runtime.credentials.export_api_keys()}
        )


async def _async_remove_credential(call: Any) -> None:
    runtime: SuiteRuntime = call.hass.data[DOMAIN][call.data["entry_id"]]
    runtime.credentials.remove(call.data["credential_id"])
    if runtime.route.coordinator.provider.credential and call.data["credential_id"] == runtime.fuel.accounts.get("nakordoni", {}).get("credential_id"):
        runtime.route.coordinator.provider.credential = None
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


async def _async_calculate_route(call: Any) -> None:
    runtime: SuiteRuntime = next(
        (value for key, value in call.hass.data[DOMAIN].items() if key != "_frontend" and isinstance(value, SuiteRuntime)),
        None,
    )
    if runtime is not None:
        await runtime.route.async_calculate(dict(call.data))


def _journal_runtime(call: Any) -> SuiteRuntime:
    runtime = call.hass.data[DOMAIN].get(call.data.get("entry_id")) if call.data.get("entry_id") else next(
        (value for value in call.hass.data[DOMAIN].values() if isinstance(value, SuiteRuntime)), None
    )
    if not isinstance(runtime, SuiteRuntime):
        raise TypeError("entry_not_loaded")
    return runtime


async def _async_journal_create_trip(call: Any) -> None:
    runtime = _journal_runtime(call)
    await call.hass.async_add_executor_job(
        runtime.journal.store.create_trip,
        call.data["vehicle_id"],
        call.data["title"],
        **{key: call.data[key] for key in ("description", "destination", "status") if key in call.data},
    )


async def _async_journal_update_trip(call: Any) -> None:
    runtime = _journal_runtime(call)
    runtime.journal.store.assert_vehicle_scope(call.data["vehicle_id"], trip_id=call.data["trip_id"])
    fields = {key: call.data[key] for key in ("title", "description", "destination", "status") if key in call.data}
    await call.hass.async_add_executor_job(runtime.journal.store.update_trip, call.data["trip_id"], **fields)


async def _async_journal_delete_trip(call: Any) -> None:
    runtime = _journal_runtime(call)
    runtime.journal.store.assert_vehicle_scope(call.data["vehicle_id"], trip_id=call.data["trip_id"])
    await call.hass.async_add_executor_job(runtime.journal.store.delete_trip, call.data["trip_id"])


async def _async_journal_create_stay(call: Any) -> None:
    runtime = _journal_runtime(call)
    fields = {key: call.data[key] for key in ("trip_id", "name") if key in call.data}
    await call.hass.async_add_executor_job(runtime.journal.store.create_stay, call.data["vehicle_id"], **fields)


async def _async_journal_create_stop(call: Any) -> None:
    runtime = _journal_runtime(call)
    fields = {key: call.data[key] for key in ("trip_id", "name", "category") if key in call.data}
    await call.hass.async_add_executor_job(runtime.journal.store.create_stop, call.data["vehicle_id"], **fields)


async def _async_journal_create_expense(call: Any) -> None:
    runtime = _journal_runtime(call)
    fields = {key: call.data[key] for key in ("trip_id", "category", "amount_minor", "currency", "note") if key in call.data}
    await call.hass.async_add_executor_job(runtime.journal.store.create_expense, call.data["vehicle_id"], **fields)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    runtime: SuiteRuntime = hass.data[DOMAIN].pop(entry.entry_id)
    await runtime.fuel.async_unload()
    await runtime.journal.async_stop()
    await runtime.modules.async_unload()
    await hass.async_add_executor_job(runtime.store.close)
    if not any(key != "_frontend" for key in hass.data[DOMAIN]):
        await async_unregister_frontend(hass)
    return True

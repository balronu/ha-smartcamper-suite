from __future__ import annotations

import asyncio
import logging
import time
from typing import Any
from uuid import uuid4

import voluptuous as vol
from aiohttp import ClientError
from homeassistant import config_entries
from homeassistant.helpers import config_entry_oauth2_flow, selector

from .const import CONF_NAKORDONI_AUTH_METHOD, DEFAULT_MODULES, DOMAIN, ModuleName
from .models import Vehicle

_LOGGER = logging.getLogger(__name__)
_MODULE_KEYS = tuple(module.value for module in ModuleName)
_PROVIDERS = ("tankerkoenig", "petromap", "nakordoni")
_FUEL_TYPES = ("diesel", "e5", "e10", "lpg", "hvo100")
_PROVIDER_OPTIONS = [selector.SelectOptionDict(value=key, label=label) for key, label in (
    ("tankerkoenig", "Tankerkönig"), ("petromap", "Petromap"), ("nakordoni", "Nakordoni")
)]


def _optional_number(value: Any) -> float | None:
    if value in (None, "", 0, 0.0):
        return None
    return float(value)


def _stored_enabled(data: dict[str, Any], options: dict[str, Any]) -> list[str]:
    explicit = options.get("enabled_providers")
    if isinstance(explicit, list):
        return [provider for provider in explicit if provider in _PROVIDERS]
    accounts = options.get("provider_accounts", {})
    credentials = data.get("credentials", {})
    return [provider for provider in _PROVIDERS if provider in accounts or any(
        value.get("provider") == provider for value in credentials.values() if isinstance(value, dict)
    )]


def _vehicle_schema(current: Vehicle | None = None) -> vol.Schema:
    current = current or Vehicle.create("Wohnmobil")
    return vol.Schema({
        vol.Required("name", default=current.name): vol.All(str, vol.Length(min=1, max=80)),
        vol.Optional("tracker_entity_id", default=current.tracker_entity_id): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="device_tracker")
        ),
        vol.Optional("length_m", default=current.length_m): selector.NumberSelector(
            selector.NumberSelectorConfig(min=0.1, max=30, step=0.01, mode=selector.NumberSelectorMode.BOX)
        ),
        vol.Optional("width_m", default=current.width_m): selector.NumberSelector(
            selector.NumberSelectorConfig(min=0.1, max=5, step=0.01, mode=selector.NumberSelectorMode.BOX)
        ),
        vol.Optional("height_m", default=current.height_m): selector.NumberSelector(
            selector.NumberSelectorConfig(min=0.1, max=6, step=0.01, mode=selector.NumberSelectorMode.BOX)
        ),
        vol.Optional("weight_t", default=current.weight_t): selector.NumberSelector(
            selector.NumberSelectorConfig(min=0.1, max=100, step=0.1, mode=selector.NumberSelectorMode.BOX)
        ),
        vol.Optional("axle_count", default=str(current.axle_count) if current.axle_count else "2"): selector.SelectSelector(
            selector.SelectSelectorConfig(options=[str(value) for value in range(1, 7)], mode=selector.SelectSelectorMode.DROPDOWN)
        ),
        vol.Required("fuel_types", default=current.fuel_types or ["diesel"]): selector.SelectSelector(
            selector.SelectSelectorConfig(options=list(_FUEL_TYPES), multiple=True, mode=selector.SelectSelectorMode.DROPDOWN)
        ),
    })


def _provider_selection_schema(current: list[str]) -> vol.Schema:
    return vol.Schema({
        vol.Required("enabled_providers", default=current): selector.SelectSelector(
            selector.SelectSelectorConfig(options=_PROVIDER_OPTIONS, multiple=True, mode=selector.SelectSelectorMode.LIST)
        )
    })


def _provider_credentials_schema(enabled: list[str], *, include_oauth: bool = True) -> vol.Schema:
    fields: dict[Any, Any] = {}
    for provider in enabled:
        fields[vol.Optional(f"{provider}_api_key", default="")] = selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
        )
    if include_oauth and "nakordoni" in enabled:
        fields[vol.Optional("nakordoni_oauth", default=False)] = bool
    return vol.Schema(fields)


def _vehicle_manager_schema(vehicles: list[dict[str, Any]]) -> vol.Schema:
    choices = [selector.SelectOptionDict(value="add", label="Fahrzeug hinzufügen")]
    if vehicles:
        choices.extend([
            selector.SelectOptionDict(value="edit", label="Fahrzeug bearbeiten"),
            selector.SelectOptionDict(value="remove", label="Fahrzeug entfernen"),
        ])
    choices.append(selector.SelectOptionDict(value="done", label="Fertig"))
    fields: dict[Any, Any] = {
        vol.Required("action", default="add"): selector.SelectSelector(
            selector.SelectSelectorConfig(options=choices, mode=selector.SelectSelectorMode.DROPDOWN)
        )
    }
    if vehicles:
        fields[vol.Optional("vehicle_id", default=vehicles[0]["vehicle_id"])] = selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[selector.SelectOptionDict(value=item["vehicle_id"], label=item["name"]) for item in vehicles],
                mode=selector.SelectSelectorMode.DROPDOWN,
            )
        )
    return vol.Schema(fields)


def _module_schema(current: dict[str, bool] | None = None) -> vol.Schema:
    current = current or dict(DEFAULT_MODULES)
    return vol.Schema({
        vol.Required("travel_journal", default=bool(current.get("travel_journal"))): bool,
        vol.Required("fuel_stations", default=bool(current.get("fuel_stations"))): bool,
        vol.Required("route_planner", default=bool(current.get("route_planner"))): bool,
    })


def _common_schema(current: dict[str, Any] | None = None) -> vol.Schema:
    current = current or {}
    return vol.Schema({
        vol.Required("refresh_mode", default=current.get("refresh_mode", "automatic")): vol.In(("automatic", "movement", "manual")),
        vol.Required("refresh_interval_min", default=current.get("refresh_interval_min", 15)): vol.All(vol.Coerce(int), vol.Range(min=1, max=1440)),
    })


def _normalise_vehicle(user_input: dict[str, Any], vehicle_id: str | None = None) -> dict[str, Any]:
    fuel_types = user_input.get("fuel_types", ["diesel"])
    if isinstance(fuel_types, str):
        fuel_types = [item.strip() for item in fuel_types.split(",") if item.strip()]
    vehicle = Vehicle(
        vehicle_id=vehicle_id or uuid4().hex,
        name=str(user_input["name"]).strip(),
        tracker_entity_id=str(user_input.get("tracker_entity_id") or "").strip() or None,
        fuel_types=list(fuel_types),
        length_m=_optional_number(user_input.get("length_m")),
        width_m=_optional_number(user_input.get("width_m")),
        height_m=_optional_number(user_input.get("height_m")),
        weight_t=_optional_number(user_input.get("weight_t")),
        axle_count=int(user_input.get("axle_count")) if user_input.get("axle_count") not in (None, "") else None,
    )
    vehicle.validate()
    return vehicle.to_dict()


def _credentials(provider_input: dict[str, Any], enabled: list[str], existing: dict[str, Any] | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    credentials = dict(existing or {})
    accounts: dict[str, Any] = {}
    for provider in enabled:
        credential_id = f"{provider}-api-key"
        api_key = str(provider_input.get(f"{provider}_api_key", "")).strip()
        if api_key:
            credentials[credential_id] = {"provider": provider, "api_key": api_key}
        if credential_id in credentials:
            accounts[provider] = {"credential_id": credential_id}
    return credentials, accounts


class SmartCamperConfigFlow(config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN):
    DOMAIN = DOMAIN
    VERSION = 1

    @property
    def logger(self) -> logging.Logger:
        return _LOGGER

    async def _async_start_nakordoni_oauth(self, pending_data: dict[str, Any]):
        implementations = await config_entry_oauth2_flow.async_get_implementations(self.hass, DOMAIN)
        implementation = implementations.get("nakordoni")
        if implementation is None:
            return self.async_abort(reason="oauth_implementation_unavailable")
        self.flow_impl = implementation
        self._oauth_pending_data = dict(pending_data)
        return await self.async_step_auth()

    async def async_step_creation(self, user_input: dict[str, Any] | None = None):
        try:
            async with asyncio.timeout(30):
                token = await self.flow_impl.async_resolve_external_data(self.external_data)
        except TimeoutError:
            return self.async_abort(reason="oauth_timeout")
        except (ClientError, KeyError, TypeError, ValueError):
            _LOGGER.error("Nakordoni OAuth token exchange failed")
            return self.async_abort(reason="oauth_failed")
        if not isinstance(token, dict) or "expires_in" not in token:
            return self.async_abort(reason="oauth_error")
        try:
            expires_in = int(token["expires_in"])
        except (TypeError, ValueError):
            return self.async_abort(reason="oauth_error")
        token = {**token, "expires_in": expires_in, "expires_at": time.time() + expires_in}
        pending = dict(getattr(self, "_oauth_pending_data", {}))
        pending["_data"] = {**pending["_data"], "token": token, "auth_implementation": self.flow_impl.domain, CONF_NAKORDONI_AUTH_METHOD: "oauth2"}
        return self.async_create_entry(title="SmartCamper Suite", data=pending["_data"], options=pending["_options"])

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        self._flow_data = {"vehicles": []}
        return await self.async_step_providers()

    async def async_step_providers(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            self._flow_data["enabled_providers"] = list(user_input.get("enabled_providers", []))
            return await self.async_step_provider_credentials()
        return self.async_show_form(step_id="providers", data_schema=_provider_selection_schema([]))

    async def async_step_provider_credentials(self, user_input: dict[str, Any] | None = None):
        enabled = self._flow_data["enabled_providers"]
        if user_input is not None:
            credentials, accounts = _credentials(user_input, enabled)
            self._flow_data.update({"credentials": credentials, "provider_accounts": accounts, "nakordoni_oauth": bool(user_input.get("nakordoni_oauth"))})
            return await self.async_step_vehicles()
        return self.async_show_form(step_id="provider_credentials", data_schema=_provider_credentials_schema(enabled))

    async def async_step_vehicles(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            action = user_input["action"]
            if action == "add":
                return await self.async_step_vehicle()
            if action == "done" and self._flow_data["vehicles"]:
                return await self.async_step_modules()
            if action in {"edit", "remove"}:
                vehicle_id = user_input.get("vehicle_id")
                if action == "remove":
                    self._flow_data["vehicles"] = [item for item in self._flow_data["vehicles"] if item["vehicle_id"] != vehicle_id]
                    return await self.async_step_vehicles()
                self._editing_vehicle_id = vehicle_id
                return await self.async_step_vehicle()
        return self.async_show_form(step_id="vehicles", data_schema=_vehicle_manager_schema(self._flow_data["vehicles"]))

    async def async_step_vehicle(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            vehicle = _normalise_vehicle(user_input, getattr(self, "_editing_vehicle_id", None))
            vehicles = [item for item in self._flow_data["vehicles"] if item["vehicle_id"] != vehicle["vehicle_id"]]
            vehicles.append(vehicle)
            self._flow_data["vehicles"] = vehicles
            self._editing_vehicle_id = None
            return await self.async_step_vehicles()
        current = next((item for item in self._flow_data["vehicles"] if item["vehicle_id"] == getattr(self, "_editing_vehicle_id", None)), None)
        return self.async_show_form(step_id="vehicle", data_schema=_vehicle_schema(Vehicle.from_dict(current) if current else None))

    async def async_step_modules(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            self._flow_data["modules"] = {key: bool(user_input.get(key, False)) for key in _MODULE_KEYS}
            return await self.async_step_common()
        return self.async_show_form(step_id="modules", data_schema=_module_schema())

    async def async_step_common(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            options = {"vehicles": self._flow_data["vehicles"], "enabled_providers": self._flow_data["enabled_providers"], "provider_accounts": self._flow_data["provider_accounts"], "modules": self._flow_data["modules"], **user_input}
            data = {"credentials": self._flow_data["credentials"]}
            if self._flow_data.get("nakordoni_oauth"):
                return await self._async_start_nakordoni_oauth({"_data": data, "_options": options})
            return self.async_create_entry(title="SmartCamper Suite", data=data, options=options)
        return self.async_show_form(step_id="common", data_schema=_common_schema())

    @staticmethod
    def async_get_options_flow(config_entry):
        return SmartCamperOptionsFlow()


class SmartCamperOptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        self._flow_data = {"vehicles": [dict(item) for item in self.config_entry.options.get("vehicles", [])], "enabled_providers": _stored_enabled(self.config_entry.data, self.config_entry.options)}
        return await self.async_step_providers()

    async def async_step_providers(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            self._flow_data["enabled_providers"] = list(user_input.get("enabled_providers", []))
            return await self.async_step_provider_credentials()
        return self.async_show_form(step_id="providers", data_schema=_provider_selection_schema(self._flow_data["enabled_providers"]))

    async def async_step_provider_credentials(self, user_input: dict[str, Any] | None = None):
        enabled = self._flow_data["enabled_providers"]
        if user_input is not None:
            credentials, accounts = _credentials(user_input, enabled, self.config_entry.data.get("credentials"))
            self._flow_data.update({"credentials": credentials, "provider_accounts": accounts, "nakordoni_oauth": bool(user_input.get("nakordoni_oauth"))})
            return await self.async_step_vehicles()
        return self.async_show_form(step_id="provider_credentials", data_schema=_provider_credentials_schema(enabled, include_oauth=False))

    async def async_step_vehicles(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            action = user_input["action"]
            if action == "add":
                return await self.async_step_vehicle()
            if action == "done" and self._flow_data["vehicles"]:
                return await self.async_step_modules()
            vehicle_id = user_input.get("vehicle_id")
            if action == "remove":
                self._flow_data["vehicles"] = [item for item in self._flow_data["vehicles"] if item["vehicle_id"] != vehicle_id]
                return await self.async_step_vehicles()
            if action == "edit":
                self._editing_vehicle_id = vehicle_id
                return await self.async_step_vehicle()
        return self.async_show_form(step_id="vehicles", data_schema=_vehicle_manager_schema(self._flow_data["vehicles"]))

    async def async_step_vehicle(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            vehicle = _normalise_vehicle(user_input, getattr(self, "_editing_vehicle_id", None))
            vehicles = [item for item in self._flow_data["vehicles"] if item["vehicle_id"] != vehicle["vehicle_id"]]
            vehicles.append(vehicle)
            self._flow_data["vehicles"] = vehicles
            self._editing_vehicle_id = None
            return await self.async_step_vehicles()
        current = next((item for item in self._flow_data["vehicles"] if item["vehicle_id"] == getattr(self, "_editing_vehicle_id", None)), None)
        return self.async_show_form(step_id="vehicle", data_schema=_vehicle_schema(Vehicle.from_dict(current) if current else None))

    async def async_step_modules(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            self._flow_data["modules"] = {key: bool(user_input.get(key, False)) for key in _MODULE_KEYS}
            return await self.async_step_common()
        return self.async_show_form(step_id="modules", data_schema=_module_schema(self.config_entry.options.get("modules")))

    async def async_step_common(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            options = {**self.config_entry.options, "vehicles": self._flow_data["vehicles"], "enabled_providers": self._flow_data["enabled_providers"], "provider_accounts": self._flow_data["provider_accounts"], "modules": self._flow_data["modules"], **user_input}
            self.hass.config_entries.async_update_entry(self.config_entry, data={**self.config_entry.data, "credentials": self._flow_data["credentials"]})
            return self.async_create_entry(title="", data=options)
        return self.async_show_form(step_id="common", data_schema=_common_schema(self.config_entry.options))

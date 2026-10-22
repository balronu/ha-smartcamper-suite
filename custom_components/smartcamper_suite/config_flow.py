from __future__ import annotations

import asyncio
import logging
import time
from typing import Any
from uuid import uuid4

import voluptuous as vol
from aiohttp import ClientError
from homeassistant import config_entries
from homeassistant.helpers import config_entry_oauth2_flow

from .const import CONF_NAKORDONI_AUTH_METHOD, DEFAULT_MODULES, DOMAIN, ModuleName
from .models import Vehicle

_LOGGER = logging.getLogger(__name__)
_MODULE_KEYS = tuple(module.value for module in ModuleName)
_PROVIDERS = ("tankerkoenig", "petromap", "nakordoni")


def _optional_number(value: float) -> float | None:
    return None if value == 0 else value


def _vehicle_schema(current: Vehicle | None = None) -> vol.Schema:
    current = current or Vehicle.create("Wohnmobil")
    return vol.Schema({
        vol.Required("name", default=current.name): vol.All(str, vol.Length(min=1, max=80)),
        vol.Optional("tracker_entity_id", default=current.tracker_entity_id or ""): str,
        vol.Optional("length_m", default=current.length_m or 0): vol.All(vol.Coerce(float), vol.Range(min=0, max=30)),
        vol.Optional("width_m", default=current.width_m or 0): vol.All(vol.Coerce(float), vol.Range(min=0, max=5)),
        vol.Optional("height_m", default=current.height_m or 0): vol.All(vol.Coerce(float), vol.Range(min=0, max=6)),
        vol.Optional("weight_t", default=current.weight_t or 0): vol.All(vol.Coerce(float), vol.Range(min=0, max=100)),
        vol.Optional("axle_count", default=current.axle_count or 0): vol.All(vol.Coerce(int), vol.Range(min=0, max=10)),
        vol.Optional("fuel_types", default=",".join(current.fuel_types or ["diesel"])): str,
    })


def _provider_schema() -> vol.Schema:
    return vol.Schema({
        vol.Optional("tankerkoenig_api_key", default=""): str,
        vol.Optional("petromap_api_key", default=""): str,
        vol.Optional("nakordoni_api_key", default=""): str,
        vol.Optional("nakordoni_oauth", default=False): bool,
    })


def _module_schema(current: dict[str, bool] | None = None) -> vol.Schema:
    current = current or dict(DEFAULT_MODULES)
    return vol.Schema({
        vol.Optional("travel_journal", default=bool(current.get("travel_journal"))): bool,
        vol.Optional("fuel_stations", default=bool(current.get("fuel_stations"))): bool,
        vol.Optional("route_planner", default=bool(current.get("route_planner"))): bool,
    })


def _common_schema(current: dict[str, Any] | None = None) -> vol.Schema:
    current = current or {}
    return vol.Schema({
        vol.Optional("refresh_mode", default=current.get("refresh_mode", "automatic")): vol.In(("automatic", "movement", "manual")),
        vol.Optional("refresh_interval_min", default=current.get("refresh_interval_min", 15)): vol.All(vol.Coerce(int), vol.Range(min=1, max=1440)),
        vol.Optional("journal_legacy_import", default=False): vol.In((False,)),
    })


def _normalise_vehicle(user_input: dict[str, Any], vehicle_id: str | None = None) -> dict[str, Any]:
    fuel_types = [item.strip() for item in str(user_input.get("fuel_types", "diesel")).split(",") if item.strip()]
    vehicle = Vehicle(
        vehicle_id=vehicle_id or uuid4().hex,
        name=str(user_input["name"]).strip(),
        tracker_entity_id=str(user_input.get("tracker_entity_id", "")).strip() or None,
        fuel_types=fuel_types,
        length_m=_optional_number(float(user_input.get("length_m", 0))),
        width_m=_optional_number(float(user_input.get("width_m", 0))),
        height_m=_optional_number(float(user_input.get("height_m", 0))),
        weight_t=_optional_number(float(user_input.get("weight_t", 0))),
        axle_count=int(user_input.get("axle_count", 0)) or None,
    )
    vehicle.validate()
    return vehicle.to_dict()


def _credentials(provider_input: dict[str, Any], existing: dict[str, Any] | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    credentials = dict(existing or {})
    accounts: dict[str, Any] = {}
    for provider in _PROVIDERS:
        api_key = str(provider_input.get(f"{provider}_api_key", "")).strip()
        credential_id = f"{provider}-api-key"
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
        options = pending.pop("_options", {})
        pending.update({"auth_implementation": self.flow_impl.domain, "token": token, CONF_NAKORDONI_AUTH_METHOD: "oauth2"})
        return self.async_create_entry(title="SmartCamper Suite", data=pending, options=options)

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        return await self.async_step_vehicle(user_input)

    async def async_step_vehicle(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            self._flow_data = {"vehicle": _normalise_vehicle(user_input)}
            return await self.async_step_providers()
        return self.async_show_form(step_id="vehicle", data_schema=_vehicle_schema())

    async def async_step_providers(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            credentials, accounts = _credentials(user_input)
            self._flow_data.update({"credentials": credentials, "provider_accounts": accounts})
            if user_input.get("nakordoni_oauth"):
                self._flow_data["_options"] = {"vehicles": [self._flow_data["vehicle"]], "provider_accounts": accounts, "modules": dict(DEFAULT_MODULES)}
                return await self._async_start_nakordoni_oauth(self._flow_data)
            return await self.async_step_modules()
        return self.async_show_form(step_id="providers", data_schema=_provider_schema())

    async def async_step_modules(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            self._flow_data["modules"] = {key: bool(user_input.get(key, False)) for key in _MODULE_KEYS}
            return await self.async_step_common()
        return self.async_show_form(step_id="modules", data_schema=_module_schema())

    async def async_step_common(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            options = {
                "vehicles": [self._flow_data["vehicle"]],
                "provider_accounts": self._flow_data["provider_accounts"],
                "modules": self._flow_data["modules"],
                "refresh_mode": user_input["refresh_mode"],
                "refresh_interval_min": user_input["refresh_interval_min"],
                "journal_legacy_import": False,
            }
            return self.async_create_entry(title="SmartCamper Suite", data={"credentials": self._flow_data["credentials"]}, options=options)
        return self.async_show_form(step_id="common", data_schema=_common_schema())

    @staticmethod
    def async_get_options_flow(config_entry):
        return SmartCamperOptionsFlow()


class SmartCamperOptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        self._flow_data = {}
        return await self.async_step_vehicle(user_input)

    def _current_vehicle(self) -> Vehicle | None:
        values = self.config_entry.options.get("vehicles", [])
        if not values:
            return None
        try:
            return Vehicle.from_dict(values[0])
        except (TypeError, ValueError, KeyError):
            return None

    async def async_step_vehicle(self, user_input: dict[str, Any] | None = None):
        current = self._current_vehicle()
        if user_input is not None:
            self._flow_data["vehicle"] = _normalise_vehicle(user_input, current.vehicle_id if current else None)
            return await self.async_step_providers()
        return self.async_show_form(step_id="vehicle", data_schema=_vehicle_schema(current))

    async def async_step_providers(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            credentials, accounts = _credentials(user_input, self.config_entry.data.get("credentials"))
            self._flow_data.update({"credentials": credentials, "provider_accounts": accounts})
            return await self.async_step_modules()
        return self.async_show_form(step_id="providers", data_schema=_provider_schema())

    async def async_step_modules(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            self._flow_data["modules"] = {key: bool(user_input.get(key, False)) for key in _MODULE_KEYS}
            return await self.async_step_common()
        return self.async_show_form(step_id="modules", data_schema=_module_schema(self.config_entry.options.get("modules")))

    async def async_step_common(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            options = {
                **self.config_entry.options,
                "vehicles": [self._flow_data["vehicle"]],
                "provider_accounts": self._flow_data["provider_accounts"],
                "modules": self._flow_data["modules"],
                "refresh_mode": user_input["refresh_mode"],
                "refresh_interval_min": user_input["refresh_interval_min"],
                "journal_legacy_import": False,
            }
            update_entry = getattr(self.hass.config_entries, "async_update_entry", None)
            if update_entry is not None:
                update_entry(self.config_entry, data={"credentials": self._flow_data["credentials"]})
            return self.async_create_entry(title="", data=options)
        return self.async_show_form(step_id="common", data_schema=_common_schema(self.config_entry.options))

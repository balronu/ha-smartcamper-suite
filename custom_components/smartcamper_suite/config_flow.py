from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import voluptuous as vol
from aiohttp import ClientError
from homeassistant import config_entries
from homeassistant.helpers import config_entry_oauth2_flow

from .const import CONF_NAKORDONI_AUTH_METHOD, DEFAULT_MODULES, DOMAIN

_LOGGER = logging.getLogger(__name__)


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
        """Resolve Nakordoni OAuth without logging or exposing token contents."""
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
        data = dict(getattr(self, "_oauth_pending_data", {}))
        data.update({"auth_implementation": self.flow_impl.domain, "token": token, CONF_NAKORDONI_AUTH_METHOD: "oauth2"})
        return self.async_create_entry(title="SmartCamper Suite", data=data)

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        if user_input is not None:
            if user_input.get("nakordoni_oauth"):
                return await self._async_start_nakordoni_oauth(user_input)
            return self.async_create_entry(title="SmartCamper Suite", data={}, options={"modules": dict(DEFAULT_MODULES), "vehicles": [], "providers": {}})
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Optional("nakordoni_oauth", default=False): bool}),
        )

    @staticmethod
    def async_get_options_flow(config_entry):
        return SmartCamperOptionsFlow()


class SmartCamperOptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            return self.async_create_entry(title="", data={**self.config_entry.options, "modules": user_input})
        return self.async_show_form(step_id="init", data_schema=vol.Schema({vol.Optional(key, default=value): bool for key, value in self.config_entry.options.get("modules", DEFAULT_MODULES).items()}))

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries

from .const import DEFAULT_MODULES, DOMAIN


class SmartCamperConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        if user_input is not None:
            return self.async_create_entry(title="SmartCamper Suite", data={}, options={"modules": dict(DEFAULT_MODULES), "vehicles": [], "providers": {}})
        return self.async_show_form(step_id="user", data_schema=vol.Schema({}))

    @staticmethod
    def async_get_options_flow(config_entry):
        return SmartCamperOptionsFlow()


class SmartCamperOptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            return self.async_create_entry(title="", data={**self.config_entry.options, "modules": user_input})
        return self.async_show_form(step_id="init", data_schema=vol.Schema({vol.Optional(key, default=value): bool for key, value in self.config_entry.options.get("modules", DEFAULT_MODULES).items()}))

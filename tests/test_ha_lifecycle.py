import asyncio
import sqlite3
from types import MappingProxyType, SimpleNamespace

import pytest
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from custom_components.smartcamper_suite import async_setup_entry, async_unload_entry
from custom_components.smartcamper_suite.config_flow import SmartCamperConfigFlow, SmartCamperOptionsFlow
from custom_components.smartcamper_suite.const import DEFAULT_MODULES, DOMAIN, ModuleName
from custom_components.smartcamper_suite.frontend import (
    LOGO_URL,
    RESOURCE_URL,
    async_register_frontend,
    async_unregister_frontend,
)


def make_entry(options=None):
    return ConfigEntry(
        data={},
        domain=DOMAIN,
        title="SmartCamper Suite",
        source="user",
        version=1,
        minor_version=0,
        options=options or {"modules": dict(DEFAULT_MODULES)},
        entry_id="suite-test",
        unique_id=None,
        discovery_keys=MappingProxyType({}),
        subentries_data=None,
    )


def test_home_assistant_setup_unload_closes_store_and_preserves_module_isolation(tmp_path):
    async def run():
        hass = HomeAssistant(str(tmp_path))
        entry = make_entry({"modules": {ModuleName.ROUTE_PLANNER.value: True}})

        assert await async_setup_entry(hass, entry)
        runtime = hass.data[DOMAIN][entry.entry_id]
        assert runtime.modules.modules[ModuleName.ROUTE_PLANNER].started
        assert not runtime.modules.modules[ModuleName.FUEL_STATIONS].started
        assert (tmp_path / ".storage" / "smartcamper_suite.sqlite").is_file()
        assert (tmp_path / ".storage" / "smartcamper_suite_travel_journal.sqlite").is_file()

        connection = runtime.store.connection
        journal_connection = runtime.journal.store.connection
        assert await async_unload_entry(hass, entry)
        with pytest.raises(sqlite3.ProgrammingError):
            connection.execute("SELECT 1")
        with pytest.raises(sqlite3.ProgrammingError):
            journal_connection.execute("SELECT 1")

    asyncio.run(run())


def test_config_flow_and_options_flow_are_available_without_credentials():
    async def run():
        hass = SimpleNamespace(
            config_entries=SimpleNamespace(async_entries=lambda *args, **kwargs: [])
        )
        flow = SmartCamperConfigFlow()
        flow.hass = hass
        flow.context = {}
        form = await flow.async_step_user()
        assert form["type"] == "form"
        result = await flow.async_step_user({})
        assert result["type"] == "create_entry"
        assert result["options"]["modules"] == dict(DEFAULT_MODULES)

        existing = SmartCamperConfigFlow()
        existing.hass = SimpleNamespace(
            config_entries=SimpleNamespace(async_entries=lambda *args, **kwargs: [make_entry()])
        )
        existing.context = {}
        assert (await existing.async_step_user())["reason"] == "single_instance_allowed"

        config_entry = make_entry()
        options = SmartCamperOptionsFlow()
        options.hass = SimpleNamespace(
            config_entries=SimpleNamespace(async_get_known_entry=lambda _entry_id: config_entry)
        )
        options.handler = config_entry.entry_id
        option_result = await options.async_step_init({ModuleName.ROUTE_PLANNER.value: True})
        assert option_result["type"] == "create_entry"
        assert option_result["data"]["modules"][ModuleName.ROUTE_PLANNER.value] is True

    asyncio.run(run())


def test_frontend_registration_is_idempotent_across_reload():
    async def run():
        static_calls = []
        added = []
        removed = []
        hass = SimpleNamespace(
            data={},
            http=SimpleNamespace(async_register_static_paths=lambda paths: static_calls.append(paths)),
            frontend=SimpleNamespace(
                add_extra_js_url=lambda url: added.append(url),
                remove_extra_js_url=lambda url: removed.append(url),
            ),
        )

        async def register(paths):
            static_calls.append(paths)

        hass.http.async_register_static_paths = register
        await async_register_frontend(hass)
        assert [config.url_path for config in static_calls[0]] == [RESOURCE_URL, LOGO_URL]
        await async_unregister_frontend(hass)
        await async_register_frontend(hass)
        assert len(static_calls) == 1
        assert added == [RESOURCE_URL, RESOURCE_URL]
        assert removed == [RESOURCE_URL]

    asyncio.run(run())

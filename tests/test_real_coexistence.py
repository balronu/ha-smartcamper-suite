"""Opt-in real HA coexistence harness for local QA."""

import asyncio
import os
import shutil
import tempfile
from pathlib import Path
from types import MappingProxyType

import pytest
from homeassistant import loader
from homeassistant.components.frontend import DATA_EXTRA_JS_URL_ES5, DATA_EXTRA_MODULE_URL, DATA_PANELS, UrlManager
from homeassistant.config_entries import ConfigEntry
from homeassistant.setup import async_setup_component

try:
    from pytest_homeassistant_custom_component.common import async_test_home_assistant
except ImportError:  # pragma: no cover - optional local QA dependency
    pytest.skip("pytest-homeassistant-custom-component is required for opt-in coexistence QA", allow_module_level=True)


def test_real_four_integration_coexistence():
    if os.environ.get("SMARTCAMPER_RUN_COEXISTENCE") != "1":
        pytest.skip("opt-in: SMARTCAMPER_RUN_COEXISTENCE=1")

    async def run() -> None:
        repository = Path(__file__).parents[1]
        workspace = repository.parent
        sources = {
            "mobile_fuel_stations": workspace / "ha-mobile-fuel-stations" / "custom_components" / "mobile_fuel_stations",
            "camper_route_planner": workspace / "work" / "ha-camper-route-planner" / "custom_components" / "camper_route_planner",
            "camper_travel_journal": workspace / "work" / "ha-camper-travel-journal" / "custom_components" / "camper_travel_journal",
            "smartcamper_suite": repository / "custom_components" / "smartcamper_suite",
        }
        root = Path(tempfile.mkdtemp(prefix="smartcamper-real-coexistence-"))
        try:
            target = root / "custom_components"
            target.mkdir(parents=True)
            for domain, source in sources.items():
                if not source.is_dir():
                    pytest.skip(f"missing read-only source checkout: {source}")
                shutil.copytree(source, target / domain)
            import custom_components
            custom_components.__path__.append(str(target))
            async with async_test_home_assistant(config_dir=str(root)) as hass:
                hass.data.pop(loader.DATA_CUSTOM_COMPONENTS, None)
                hass.data[DATA_EXTRA_MODULE_URL] = UrlManager(lambda *_: None, [])
                hass.data[DATA_EXTRA_JS_URL_ES5] = UrlManager(lambda *_: None, [])
                hass.data[DATA_PANELS] = {}
                assert await async_setup_component(hass, "http", {})
                assert await async_setup_component(hass, "websocket_api", {})
                results = {}
                for domain in ("mobile_fuel_stations", "camper_route_planner", "camper_travel_journal"):
                    integration = await loader.async_get_integration(hass, domain)
                    component = await integration.async_get_component()
                    results[domain] = await component.async_setup(hass, {})
                from custom_components.smartcamper_suite import async_setup_entry
                entry = ConfigEntry(data={}, domain="smartcamper_suite", title="SmartCamper Suite", source="user", version=1, minor_version=0, options={"modules": {"travel_journal": True}}, entry_id="coexistence-suite", unique_id=None, discovery_keys=MappingProxyType({}), subentries_data=None)
                results["smartcamper_suite"] = await async_setup_entry(hass, entry)
                assert results == {domain: True for domain in sources}
                assert (root / ".storage" / "smartcamper_suite_travel_journal.sqlite").is_file()
        finally:
            shutil.rmtree(root, ignore_errors=True)

    asyncio.run(run())

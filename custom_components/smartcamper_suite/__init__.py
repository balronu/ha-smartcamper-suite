from __future__ import annotations

from dataclasses import dataclass

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
from .modules import ModuleManager
from .providers import ProviderRegistry
from .storage import SuiteStore

PLATFORMS: list[str] = []


@dataclass(slots=True)
class SuiteRuntime:
    providers: ProviderRegistry
    credentials: CredentialStore
    api: ApiClient
    modules: ModuleManager
    store: SuiteStore


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    await async_register_frontend(hass)
    store = await hass.async_add_executor_job(
        SuiteStore, hass.config.path(".storage", "smartcamper_suite.sqlite")
    )
    runtime = SuiteRuntime(
        ProviderRegistry(), CredentialStore(), ApiClient(), ModuleManager(entry.options.get("modules")), store
    )
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = runtime
    await runtime.modules.async_setup(runtime)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    runtime: SuiteRuntime = hass.data[DOMAIN].pop(entry.entry_id)
    await runtime.modules.async_unload()
    await hass.async_add_executor_job(runtime.store.close)
    if not any(key != "_frontend" for key in hass.data[DOMAIN]):
        await async_unregister_frontend(hass)
    return True

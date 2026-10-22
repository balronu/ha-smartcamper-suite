from __future__ import annotations

from pathlib import Path

try:
    from homeassistant.components.http import StaticPathConfig
    from homeassistant.core import HomeAssistant
except ImportError:  # Offline domain tests do not install Home Assistant.
    StaticPathConfig = None  # type: ignore[assignment]
    HomeAssistant = object  # type: ignore[assignment,misc]

from .const import DOMAIN

RESOURCE_URL = f"/{DOMAIN}/smartcamper-card.js"
_registered = False


async def async_register_frontend(hass: HomeAssistant) -> None:
    global _registered
    if _registered or StaticPathConfig is None or not hasattr(hass, "http"):
        return
    bundle = Path(__file__).with_name("smartcamper-card.js")
    if not bundle.is_file():
        return
    await hass.http.async_register_static_paths([StaticPathConfig(RESOURCE_URL, str(bundle), cache_headers=False)])
    if hasattr(hass, "frontend"):
        hass.frontend.add_extra_js_url(RESOURCE_URL)
    _registered = True


async def async_unregister_frontend(hass: HomeAssistant) -> None:
    global _registered
    if not _registered:
        return
    if hasattr(hass, "frontend") and hasattr(hass.frontend, "remove_extra_js_url"):
        hass.frontend.remove_extra_js_url(RESOURCE_URL)
    _registered = False

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
LOGO_URL = f"/{DOMAIN}/logos"
_FRONTEND_STATE = "_frontend"


async def async_register_frontend(hass: HomeAssistant) -> None:
    if StaticPathConfig is None or getattr(hass, "http", None) is None:
        return
    domain_data = hass.data.setdefault(DOMAIN, {})
    state = domain_data.get(_FRONTEND_STATE)
    if state is not None:
        if not state["active"] and hasattr(hass, "frontend"):
            hass.frontend.add_extra_js_url(RESOURCE_URL)
        state["active"] = True
        return
    bundle = Path(__file__).with_name("smartcamper-card.js")
    logos = Path(__file__).with_name("logos")
    if not bundle.is_file() or not logos.is_dir():
        return
    await hass.http.async_register_static_paths(
        [
            StaticPathConfig(RESOURCE_URL, str(bundle), cache_headers=False),
            StaticPathConfig(LOGO_URL, str(logos), cache_headers=True),
        ]
    )
    if hasattr(hass, "frontend"):
        hass.frontend.add_extra_js_url(RESOURCE_URL)
    domain_data[_FRONTEND_STATE] = {"active": True}


async def async_unregister_frontend(hass: HomeAssistant) -> None:
    state = hass.data.get(DOMAIN, {}).get(_FRONTEND_STATE)
    if state is None or not state["active"]:
        return
    if hasattr(hass, "frontend") and hasattr(hass.frontend, "remove_extra_js_url"):
        hass.frontend.remove_extra_js_url(RESOURCE_URL)
    state["active"] = False

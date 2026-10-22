"""Authenticated WebSocket boundary for the Suite journal module."""

from __future__ import annotations

from typing import Any

try:
    import voluptuous as vol
    from homeassistant.components import websocket_api
except ImportError:  # pragma: no cover - pure domain tests
    websocket_api = None  # type: ignore[assignment]
    vol = None  # type: ignore[assignment]

from . import SuiteRuntime
from .const import DOMAIN


def async_register(hass: Any) -> None:
    if websocket_api is None:
        return
    marker = hass.data.setdefault(DOMAIN, {}).setdefault("journal_api_registered", False)
    if marker:
        return

    def runtime(msg: dict[str, Any]) -> SuiteRuntime:
        selected = hass.data[DOMAIN].get(msg.get("entry_id")) if msg.get("entry_id") else next(
            (value for value in hass.data[DOMAIN].values() if isinstance(value, SuiteRuntime)), None
        )
        if not isinstance(selected, SuiteRuntime):
            raise TypeError("entry_not_loaded")
        return selected

    @websocket_api.websocket_command({"type": "smartcamper_suite/journal/list", "vehicle_id": str, vol.Optional("entry_id"): str})
    @websocket_api.async_response
    async def ws_list(hass: Any, connection: Any, msg: dict[str, Any]) -> None:
        selected = runtime(msg)
        result = await hass.async_add_executor_job(selected.journal.store.list_trips, msg["vehicle_id"])
        connection.send_result(msg["id"], {"trips": result, "summary": await hass.async_add_executor_job(selected.journal.store.summary, msg["vehicle_id"])})

    @websocket_api.websocket_command({"type": "smartcamper_suite/journal/create_trip", "vehicle_id": str, "title": str, vol.Optional("entry_id"): str, vol.Optional("description", default=""): str, vol.Optional("destination", default=""): str, vol.Optional("status", default="planned"): str})
    @websocket_api.async_response
    async def ws_create_trip(hass: Any, connection: Any, msg: dict[str, Any]) -> None:
        selected = runtime(msg)
        trip_id = await hass.async_add_executor_job(selected.journal.store.create_trip, msg["vehicle_id"], msg["title"], description=msg.get("description", ""), destination=msg.get("destination", ""), status=msg.get("status", "planned"))
        connection.send_result(msg["id"], {"trip_id": trip_id})

    for command in (ws_list, ws_create_trip):
        websocket_api.async_register_command(hass, command)
    hass.data[DOMAIN]["journal_api_registered"] = True

"""Authenticated WebSocket boundary for the Suite journal module."""

from __future__ import annotations

import base64
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

    @websocket_api.websocket_command({"type": "smartcamper_suite/journal/analyze_gpx", "vehicle_id": str, "content_base64": str, vol.Optional("entry_id"): str})
    @websocket_api.async_response
    async def ws_analyze_gpx(hass: Any, connection: Any, msg: dict[str, Any]) -> None:
        selected = runtime(msg)
        data = base64.b64decode(msg["content_base64"], validate=True)
        preview = await hass.async_add_executor_job(selected.journal.store.analyze_gpx, data, msg["vehicle_id"])
        connection.send_result(msg["id"], preview)

    @websocket_api.websocket_command({"type": "smartcamper_suite/journal/import_gpx", "vehicle_id": str, "content_base64": str, vol.Optional("trip_id"): str, vol.Optional("entry_id"): str})
    @websocket_api.async_response
    async def ws_import_gpx(hass: Any, connection: Any, msg: dict[str, Any]) -> None:
        selected = runtime(msg)
        data = base64.b64decode(msg["content_base64"], validate=True)
        preview = await hass.async_add_executor_job(selected.journal.store.analyze_gpx, data, msg["vehicle_id"])
        result = await hass.async_add_executor_job(selected.journal.store.import_gpx, preview, msg.get("trip_id"))
        connection.send_result(msg["id"], result)

    @websocket_api.websocket_command({"type": "smartcamper_suite/journal/export_pdf", "vehicle_id": str, "trip_id": str, vol.Optional("language", default="de"): str, vol.Optional("entry_id"): str})
    @websocket_api.async_response
    async def ws_export_pdf(hass: Any, connection: Any, msg: dict[str, Any]) -> None:
        selected = runtime(msg)
        pdf = await hass.async_add_executor_job(selected.journal.store.render_pdf, msg["vehicle_id"], msg["trip_id"], msg.get("language", "de"))
        connection.send_result(msg["id"], {"content_type": "application/pdf", "filename": "smartcamper-travel-journal.pdf", "pdf_base64": base64.b64encode(pdf).decode("ascii")})

    @websocket_api.websocket_command({"type": "smartcamper_suite/journal/list_suggestions", "vehicle_id": str, vol.Optional("status", default="pending"): str, vol.Optional("entry_id"): str})
    @websocket_api.async_response
    async def ws_list_suggestions(hass: Any, connection: Any, msg: dict[str, Any]) -> None:
        selected = runtime(msg)
        result = await hass.async_add_executor_job(selected.journal.store.list_suggestions, msg["vehicle_id"], msg.get("status", "pending"))
        connection.send_result(msg["id"], {"suggestions": result})

    @websocket_api.websocket_command({"type": "smartcamper_suite/journal/generate_suggestions", "vehicle_id": str, vol.Optional("trip_id"): str, vol.Optional("minimum_minutes", default=10): int, vol.Optional("radius_m", default=150.0): float, vol.Optional("entry_id"): str})
    @websocket_api.async_response
    async def ws_generate_suggestions(hass: Any, connection: Any, msg: dict[str, Any]) -> None:
        selected = runtime(msg)
        result = await hass.async_add_executor_job(selected.journal.store.generate_suggestions, msg["vehicle_id"], minimum_minutes=msg.get("minimum_minutes", 10), radius_m=msg.get("radius_m", 150.0), trip_id=msg.get("trip_id"))
        connection.send_result(msg["id"], {"suggestions": result})

    @websocket_api.websocket_command({"type": "smartcamper_suite/journal/accept_suggestion", "suggestion_id": str, vol.Optional("name", default="GPS-Stopp"): str, vol.Optional("category", default="other"): str, vol.Optional("entry_id"): str})
    @websocket_api.async_response
    async def ws_accept_suggestion(hass: Any, connection: Any, msg: dict[str, Any]) -> None:
        selected = runtime(msg)
        stop_id = await hass.async_add_executor_job(selected.journal.store.accept_suggestion, msg["suggestion_id"], name=msg.get("name", "GPS-Stopp"), category=msg.get("category", "other"))
        connection.send_result(msg["id"], {"stop_id": stop_id})

    @websocket_api.websocket_command({"type": "smartcamper_suite/journal/dismiss_suggestion", "suggestion_id": str, vol.Optional("entry_id"): str})
    @websocket_api.async_response
    async def ws_dismiss_suggestion(hass: Any, connection: Any, msg: dict[str, Any]) -> None:
        selected = runtime(msg)
        await hass.async_add_executor_job(selected.journal.store.dismiss_suggestion, msg["suggestion_id"])
        connection.send_result(msg["id"], {})

    for command in (ws_list, ws_create_trip, ws_analyze_gpx, ws_import_gpx, ws_export_pdf, ws_list_suggestions, ws_generate_suggestions, ws_accept_suggestion, ws_dismiss_suggestion):
        websocket_api.async_register_command(hass, command)
    hass.data[DOMAIN]["journal_api_registered"] = True

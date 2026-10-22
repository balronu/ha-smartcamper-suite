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

    @websocket_api.websocket_command({"type": "smartcamper_suite/journal/list", "vehicle_id": str, vol.Optional("trip_id"): str, vol.Optional("entry_id"): str})
    @websocket_api.async_response
    async def ws_list(hass: Any, connection: Any, msg: dict[str, Any]) -> None:
        selected = runtime(msg)
        vehicle_id = msg["vehicle_id"]
        trip_id = msg.get("trip_id")
        result = await hass.async_add_executor_job(selected.journal.store.list_trips, vehicle_id)
        related = await hass.async_add_executor_job(selected.journal.store.list_related, vehicle_id, trip_id)
        drives = await hass.async_add_executor_job(selected.journal.store.list_drives, vehicle_id, trip_id)
        suggestions = await hass.async_add_executor_job(selected.journal.store.list_suggestions, vehicle_id)
        connection.send_result(msg["id"], {"trips": result, "summary": await hass.async_add_executor_job(selected.journal.store.summary, vehicle_id), **related, "drives": drives, "suggestions": suggestions})

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

    @websocket_api.websocket_command({"type": "smartcamper_suite/journal/import_gpx", "vehicle_id": str, "content_base64": str, vol.Optional("trip_id"): str, vol.Optional("drive_keys", default=[]): [str], vol.Optional("entry_id"): str})
    @websocket_api.async_response
    async def ws_import_gpx(hass: Any, connection: Any, msg: dict[str, Any]) -> None:
        selected = runtime(msg)
        data = base64.b64decode(msg["content_base64"], validate=True)
        preview = await hass.async_add_executor_job(selected.journal.store.analyze_gpx, data, msg["vehicle_id"])
        result = await hass.async_add_executor_job(selected.journal.store.import_gpx, preview, msg.get("trip_id"), msg.get("drive_keys"))
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

    @websocket_api.websocket_command({"type": "smartcamper_suite/journal/list_vehicles", vol.Optional("entry_id"): str})
    @websocket_api.async_response
    async def ws_list_vehicles(_hass: Any, connection: Any, msg: dict[str, Any]) -> None:
        selected = runtime(msg)
        connection.send_result(msg["id"], {"vehicles": [{"vehicle_id": item.vehicle_id, "name": item.name, "tracker_entity_id": item.tracker_entity_id} for item in selected.journal.vehicles.values()]})

    @websocket_api.websocket_command({"type": "smartcamper_suite/journal/diagnostics", "vehicle_id": str, vol.Optional("entry_id"): str})
    @websocket_api.async_response
    async def ws_diagnostics(hass: Any, connection: Any, msg: dict[str, Any]) -> None:
        selected = runtime(msg)
        summary = await hass.async_add_executor_job(selected.journal.store.summary, msg["vehicle_id"])
        connection.send_result(msg["id"], {"database": selected.journal.store.path.name, "schema_version": 4, "module_enabled": selected.journal.enabled, "summary": summary})

    @websocket_api.websocket_command({"type": "smartcamper_suite/journal/update_trip", "trip_id": str, vol.Optional("entry_id"): str, vol.Optional("title"): str, vol.Optional("description"): str, vol.Optional("destination"): str, vol.Optional("started_at"): str, vol.Optional("ended_at"): str, vol.Optional("status"): str, vol.Optional("start_date"): str, vol.Optional("end_date"): str})
    @websocket_api.async_response
    async def ws_update_trip(hass: Any, connection: Any, msg: dict[str, Any]) -> None:
        selected = runtime(msg)
        fields = {key: value for key, value in msg.items() if key in {"title", "description", "destination", "started_at", "ended_at", "status", "start_date", "end_date"}}
        await hass.async_add_executor_job(selected.journal.store.update_trip, msg["trip_id"], **fields)
        connection.send_result(msg["id"], {})

    @websocket_api.websocket_command({"type": "smartcamper_suite/journal/delete_trip", "trip_id": str, vol.Optional("entry_id"): str})
    @websocket_api.async_response
    async def ws_delete_trip(hass: Any, connection: Any, msg: dict[str, Any]) -> None:
        selected = runtime(msg)
        await hass.async_add_executor_job(selected.journal.store.delete_trip, msg["trip_id"])
        connection.send_result(msg["id"], {})

    @websocket_api.websocket_command({"type": "smartcamper_suite/journal/create_stop", "vehicle_id": str, vol.Optional("entry_id"): str, vol.Optional("trip_id"): str, vol.Optional("name", default="Zwischenstopp"): str, vol.Optional("occurred_at"): str, vol.Optional("latitude"): float, vol.Optional("longitude"): float, vol.Optional("description", default=""): str, vol.Optional("category", default="other"): str})
    @websocket_api.async_response
    async def ws_create_stop(hass: Any, connection: Any, msg: dict[str, Any]) -> None:
        selected = runtime(msg)
        fields = {key: value for key, value in msg.items() if key in {"trip_id", "name", "occurred_at", "latitude", "longitude", "description", "category"}}
        stop_id = await hass.async_add_executor_job(selected.journal.store.create_stop, msg["vehicle_id"], **fields)
        connection.send_result(msg["id"], {"stop_id": stop_id})

    @websocket_api.websocket_command({"type": "smartcamper_suite/journal/create_expense", "vehicle_id": str, vol.Optional("entry_id"): str, vol.Optional("trip_id"): str, vol.Optional("occurred_at"): str, vol.Optional("occurred_on"): str, vol.Optional("occurred_time"): str, vol.Optional("category", default="other"): str, vol.Optional("amount_minor", default=0): int, vol.Optional("currency", default="EUR"): str, vol.Optional("note", default=""): str, vol.Optional("odometer_km"): float, vol.Optional("stay_id"): str, vol.Optional("place_id"): str})
    @websocket_api.async_response
    async def ws_create_expense(hass: Any, connection: Any, msg: dict[str, Any]) -> None:
        selected = runtime(msg)
        fields = {key: value for key, value in msg.items() if key in {"trip_id", "occurred_at", "occurred_on", "occurred_time", "category", "amount_minor", "currency", "note", "odometer_km", "stay_id", "place_id"}}
        expense_id = await hass.async_add_executor_job(selected.journal.store.create_expense, msg["vehicle_id"], **fields)
        connection.send_result(msg["id"], {"expense_id": expense_id})

    @websocket_api.websocket_command({"type": "smartcamper_suite/journal/upsert_overnight", "place_id": str, vol.Optional("entry_id"): str, vol.Optional("place_kind", default="other"): str, vol.Optional("website_url"): str, vol.Optional("booking_note"): str, vol.Optional("large_rv_suitable"): bool})
    @websocket_api.async_response
    async def ws_upsert_overnight(hass: Any, connection: Any, msg: dict[str, Any]) -> None:
        selected = runtime(msg)
        fields = {key: value for key, value in msg.items() if key in {"place_kind", "website_url", "booking_note", "large_rv_suitable"}}
        await hass.async_add_executor_job(selected.journal.store.upsert_overnight, msg["place_id"], **fields)
        connection.send_result(msg["id"], {})

    @websocket_api.websocket_command({"type": "smartcamper_suite/journal/upsert_rating", "place_id": str, "overall": int, vol.Optional("entry_id"): str, vol.Optional("large_rv_access"): int, vol.Optional("space_maneuvering"): int, vol.Optional("facilities"): int, vol.Optional("surroundings"): int, vol.Optional("review_text", default=""): str})
    @websocket_api.async_response
    async def ws_upsert_rating(hass: Any, connection: Any, msg: dict[str, Any]) -> None:
        selected = runtime(msg)
        fields = {key: value for key, value in msg.items() if key in {"large_rv_access", "space_maneuvering", "facilities", "surroundings", "review_text"}}
        await hass.async_add_executor_job(selected.journal.store.upsert_rating, msg["place_id"], msg["overall"], **fields)
        connection.send_result(msg["id"], {})

    @websocket_api.websocket_command({"type": "smartcamper_suite/journal/delete_rating", "place_id": str, vol.Optional("entry_id"): str})
    @websocket_api.async_response
    async def ws_delete_rating(hass: Any, connection: Any, msg: dict[str, Any]) -> None:
        selected = runtime(msg)
        await hass.async_add_executor_job(selected.journal.store.delete_rating, msg["place_id"])
        connection.send_result(msg["id"], {})

    @websocket_api.websocket_command({"type": "smartcamper_suite/journal/transition_trip", "trip_id": str, "status": str, vol.Optional("entry_id"): str})
    @websocket_api.async_response
    async def ws_transition_trip(hass: Any, connection: Any, msg: dict[str, Any]) -> None:
        selected = runtime(msg)
        await hass.async_add_executor_job(selected.journal.store.update_trip, msg["trip_id"], status=msg["status"])
        connection.send_result(msg["id"], {"status": msg["status"]})

    @websocket_api.websocket_command({"type": "smartcamper_suite/journal/route", "vehicle_id": str, vol.Optional("entry_id"): str, vol.Optional("trip_id"): str, vol.Optional("drive_ids"): [str], vol.Optional("max_points", default=5000): int, vol.Optional("simplify_tolerance_m", default=0.0): float})
    @websocket_api.async_response
    async def ws_route(hass: Any, connection: Any, msg: dict[str, Any]) -> None:
        selected = runtime(msg)
        result = await hass.async_add_executor_job(selected.journal.store.route_segments, msg["vehicle_id"], msg.get("trip_id"), msg.get("drive_ids"))
        points = sum(len(segment["points"]) for segment in result)
        connection.send_result(msg["id"], {"segments": result, "vehicle_id": msg["vehicle_id"], "trip_id": msg.get("trip_id"), "total_points": points, "truncated": False, "simplify_tolerance_m": msg.get("simplify_tolerance_m", 0.0)})

    @websocket_api.websocket_command({"type": "smartcamper_suite/journal/list_drives", "vehicle_id": str, vol.Optional("entry_id"): str, vol.Optional("trip_id"): str})
    @websocket_api.async_response
    async def ws_list_drives(hass: Any, connection: Any, msg: dict[str, Any]) -> None:
        selected = runtime(msg)
        result = await hass.async_add_executor_job(selected.journal.store.list_drives, msg["vehicle_id"], msg.get("trip_id"))
        connection.send_result(msg["id"], {"drives": result})

    @websocket_api.websocket_command({"type": "smartcamper_suite/journal/auto_detect_drives", "vehicle_id": str, vol.Optional("entry_id"): str})
    @websocket_api.async_response
    async def ws_auto_detect_drives(hass: Any, connection: Any, msg: dict[str, Any]) -> None:
        selected = runtime(msg)
        drive_ids = await hass.async_add_executor_job(selected.journal.store.auto_detect_drives, msg["vehicle_id"])
        connection.send_result(msg["id"], {"drive_ids": drive_ids})

    @websocket_api.websocket_command({"type": "smartcamper_suite/journal/link_drives", "trip_id": str, "drive_ids": [str], vol.Optional("entry_id"): str})
    @websocket_api.async_response
    async def ws_link_drives(hass: Any, connection: Any, msg: dict[str, Any]) -> None:
        selected = runtime(msg)
        await hass.async_add_executor_job(selected.journal.store.link_drives, msg["trip_id"], msg["drive_ids"])
        connection.send_result(msg["id"], {})

    @websocket_api.websocket_command({"type": "smartcamper_suite/journal/unlink_drive", "trip_id": str, "drive_id": str, vol.Optional("entry_id"): str})
    @websocket_api.async_response
    async def ws_unlink_drive(hass: Any, connection: Any, msg: dict[str, Any]) -> None:
        selected = runtime(msg)
        await hass.async_add_executor_job(selected.journal.store.unlink_drive, msg["trip_id"], msg["drive_id"])
        connection.send_result(msg["id"], {})

    @websocket_api.websocket_command({"type": "smartcamper_suite/journal/create_manual_drive", "vehicle_id": str, "occurred_at": str, "start_location": str, "end_location": str, "distance_km": float, vol.Optional("duration_minutes"): int, vol.Optional("trip_id"): str, vol.Optional("entry_id"): str})
    @websocket_api.async_response
    async def ws_create_manual_drive(hass: Any, connection: Any, msg: dict[str, Any]) -> None:
        selected = runtime(msg)
        drive_id = await hass.async_add_executor_job(selected.journal.store.create_manual_drive, msg["vehicle_id"], msg["occurred_at"], msg["start_location"], msg["end_location"], msg["distance_km"], msg.get("duration_minutes"), msg.get("trip_id"))
        connection.send_result(msg["id"], {"drive_id": drive_id})

    @websocket_api.websocket_command({"type": "smartcamper_suite/journal/update_manual_drive", "drive_id": str, vol.Optional("entry_id"): str, vol.Optional("started_at"): str, vol.Optional("ended_at"): str, vol.Optional("start_label"): str, vol.Optional("end_label"): str, vol.Optional("manual_distance_km"): float})
    @websocket_api.async_response
    async def ws_update_manual_drive(hass: Any, connection: Any, msg: dict[str, Any]) -> None:
        selected = runtime(msg)
        fields = {key: value for key, value in msg.items() if key in {"started_at", "ended_at", "start_label", "end_label", "manual_distance_km"}}
        await hass.async_add_executor_job(selected.journal.store.update_manual_drive, msg["drive_id"], **fields)
        connection.send_result(msg["id"], {})

    @websocket_api.websocket_command({"type": "smartcamper_suite/journal/delete_manual_drive", "drive_id": str, vol.Optional("entry_id"): str})
    @websocket_api.async_response
    async def ws_delete_manual_drive(hass: Any, connection: Any, msg: dict[str, Any]) -> None:
        selected = runtime(msg)
        await hass.async_add_executor_job(selected.journal.store.delete_manual_drive, msg["drive_id"])
        connection.send_result(msg["id"], {})

    @websocket_api.websocket_command({"type": "smartcamper_suite/journal/assign_interruption", "trip_id": str, "interruption_id": str, "status": str, vol.Optional("stop_id"): str, vol.Optional("entry_id"): str})
    @websocket_api.async_response
    async def ws_assign_interruption(hass: Any, connection: Any, msg: dict[str, Any]) -> None:
        selected = runtime(msg)
        await hass.async_add_executor_job(selected.journal.store.assign_interruption, msg["trip_id"], msg["interruption_id"], msg["status"], msg.get("stop_id"))
        connection.send_result(msg["id"], {})

    @websocket_api.websocket_command({"type": "smartcamper_suite/journal/create_stop_from_interruption", "vehicle_id": str, "trip_id": str, "interruption_id": str, "name": str, vol.Optional("place_type", default="other"): str, vol.Optional("address", default=""): str, vol.Optional("description", default=""): str, vol.Optional("entry_id"): str})
    @websocket_api.async_response
    async def ws_create_stop_from_interruption(hass: Any, connection: Any, msg: dict[str, Any]) -> None:
        selected = runtime(msg)
        stop_id = await hass.async_add_executor_job(selected.journal.store.create_stop_from_interruption, msg["vehicle_id"], msg["trip_id"], msg["interruption_id"], msg["name"], place_type=msg.get("place_type", "other"), address=msg.get("address", ""), description=msg.get("description", ""))
        connection.send_result(msg["id"], {"stop_id": stop_id})

    @websocket_api.websocket_command({"type": "smartcamper_suite/journal/update_stop", "stop_id": str, vol.Optional("entry_id"): str, vol.Optional("trip_id"): str, vol.Optional("drive_id"): str, vol.Optional("name"): str, vol.Optional("occurred_at"): str, vol.Optional("latitude"): float, vol.Optional("longitude"): float, vol.Optional("description"): str, vol.Optional("category"): str})
    @websocket_api.async_response
    async def ws_update_stop(hass: Any, connection: Any, msg: dict[str, Any]) -> None:
        selected = runtime(msg)
        fields = {key: value for key, value in msg.items() if key in {"trip_id", "drive_id", "name", "occurred_at", "latitude", "longitude", "description", "category"}}
        await hass.async_add_executor_job(selected.journal.store.update_stop, msg["stop_id"], **fields)
        connection.send_result(msg["id"], {})

    @websocket_api.websocket_command({"type": "smartcamper_suite/journal/delete_stop", "stop_id": str, vol.Optional("entry_id"): str})
    @websocket_api.async_response
    async def ws_delete_stop(hass: Any, connection: Any, msg: dict[str, Any]) -> None:
        selected = runtime(msg)
        await hass.async_add_executor_job(selected.journal.store.delete_stop, msg["stop_id"])
        connection.send_result(msg["id"], {})

    @websocket_api.websocket_command({"type": "smartcamper_suite/journal/update_expense", "expense_id": str, vol.Optional("entry_id"): str, vol.Optional("trip_id"): str, vol.Optional("occurred_at"): str, vol.Optional("occurred_on"): str, vol.Optional("occurred_time"): str, vol.Optional("category"): str, vol.Optional("amount_minor"): int, vol.Optional("currency"): str, vol.Optional("note"): str, vol.Optional("odometer_km"): float, vol.Optional("stay_id"): str, vol.Optional("place_id"): str})
    @websocket_api.async_response
    async def ws_update_expense(hass: Any, connection: Any, msg: dict[str, Any]) -> None:
        selected = runtime(msg)
        fields = {key: value for key, value in msg.items() if key in {"trip_id", "occurred_at", "occurred_on", "occurred_time", "category", "amount_minor", "currency", "note", "odometer_km", "stay_id", "place_id"}}
        await hass.async_add_executor_job(selected.journal.store.update_expense, msg["expense_id"], **fields)
        connection.send_result(msg["id"], {})

    @websocket_api.websocket_command({"type": "smartcamper_suite/journal/delete_expense", "expense_id": str, vol.Optional("entry_id"): str})
    @websocket_api.async_response
    async def ws_delete_expense(hass: Any, connection: Any, msg: dict[str, Any]) -> None:
        selected = runtime(msg)
        await hass.async_add_executor_job(selected.journal.store.delete_expense, msg["expense_id"])
        connection.send_result(msg["id"], {})

    for command in (
        ws_list, ws_create_trip, ws_analyze_gpx, ws_import_gpx, ws_export_pdf,
        ws_list_suggestions, ws_generate_suggestions, ws_accept_suggestion,
        ws_dismiss_suggestion, ws_list_vehicles, ws_diagnostics, ws_update_trip,
        ws_delete_trip, ws_create_stop, ws_create_expense, ws_upsert_overnight,
        ws_upsert_rating, ws_delete_rating, ws_transition_trip, ws_route,
        ws_list_drives, ws_auto_detect_drives, ws_link_drives, ws_unlink_drive, ws_create_manual_drive,
        ws_update_manual_drive, ws_delete_manual_drive, ws_assign_interruption,
        ws_create_stop_from_interruption, ws_update_stop, ws_delete_stop,
        ws_update_expense, ws_delete_expense,
    ):
        websocket_api.async_register_command(hass, command)
    hass.data[DOMAIN]["journal_api_registered"] = True

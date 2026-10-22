"""Offline-first route-planner module for SmartCamper Suite.

The module deliberately has no polling loop.  A route is calculated only after
an explicit service or card action and uses the suite vehicle/provider stores.
The Nakordoni motorhome contract is retained as an explicit beta boundary: the
result is never presented as legally validated motorhome navigation.
"""

from __future__ import annotations

import asyncio
import hashlib
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from xml.etree import ElementTree

from .models import Vehicle

ROUTE_ENDPOINT = "https://nakordoni.eu/api/v2/data/truck-route"
PROVIDER_NAME = "nakordoni_motorhome"
GPX_NAMESPACE = "http://www.topografix.com/GPX/1/1"
MAX_ROUTE_POINTS = 100
MAX_TRACK_POINTS = 100_000


class RouteError(RuntimeError):
    """A safe, normalized route-planner error."""

    def __init__(self, message: str, code: str, status: int | None = None, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.status = status
        self.retryable = retryable


class GpxMode(StrEnum):
    ROUTE = "route"
    TRACK = "track"
    COMBINED = "combined"


@dataclass(frozen=True, slots=True)
class Waypoint:
    latitude: float
    longitude: float
    label: str | None = None

    def __post_init__(self) -> None:
        if not -90 <= self.latitude <= 90 or not -180 <= self.longitude <= 180:
            raise ValueError("coordinates outside WGS84 bounds")

    def as_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"latitude": self.latitude, "longitude": self.longitude}
        if self.label:
            result["label"] = self.label
        return result


@dataclass(frozen=True, slots=True)
class RouteRequest:
    vehicle_id: str
    origin: Waypoint
    destination: Waypoint
    via: tuple[Waypoint, ...] = ()
    alternatives: int = 0
    traffic: str = "off"

    def __post_init__(self) -> None:
        if not self.vehicle_id or len(self.via) > 5 or not 0 <= self.alternatives <= 2:
            raise ValueError("invalid route request")

    def cache_key(self, vehicle: Vehicle) -> str:
        value = repr((self, vehicle.to_dict()))
        return hashlib.sha256(value.encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class RouteWarning:
    code: str
    message: str
    severity: str = "warning"


@dataclass(frozen=True, slots=True)
class RouteResult:
    provider: str
    distance_m: float
    duration_s: int
    geometry: tuple[Waypoint, ...]
    warnings: tuple[RouteWarning, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    synthetic: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "distance_m": self.distance_m,
            "duration_s": self.duration_s,
            "geometry": [point.as_dict() for point in self.geometry],
            "warnings": [{"code": warning.code, "message": warning.message, "severity": warning.severity} for warning in self.warnings],
            "metadata": self.metadata,
            "synthetic": self.synthetic,
        }


Transport = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


def validate_route_vehicle(vehicle: Vehicle) -> None:
    """Require the safety-critical dimensions instead of inventing defaults."""
    if vehicle.vehicle_type != "motorhome":
        raise RouteError("Das Routingmodul benötigt ein Wohnmobilprofil.", "vehicle_type_invalid")
    fields = (vehicle.length_m, vehicle.width_m, vehicle.height_m, vehicle.weight_t, vehicle.axle_count)
    if any(value is None or value <= 0 for value in fields):
        raise RouteError("Länge, Breite, Höhe, Gewicht und Achszahl sind erforderlich.", "vehicle_dimensions_missing")


def build_nakordoni_parameters(request: RouteRequest, vehicle: Vehicle) -> dict[str, Any]:
    validate_route_vehicle(vehicle)
    return {
        "from": f"{request.origin.latitude},{request.origin.longitude}",
        "to": f"{request.destination.latitude},{request.destination.longitude}",
        "via": "|".join(f"{point.latitude},{point.longitude}" for point in request.via),
        "vehicle_type": "motorhome",
        "length": vehicle.length_m,
        "width": vehicle.width_m,
        "height": vehicle.height_m,
        "weight": vehicle.weight_t,
        "axles": vehicle.axle_count,
        "traffic": request.traffic,
        "alternatives": request.alternatives,
        "geometry": "geojson",
    }


def _provider_error(payload: dict[str, Any]) -> RouteError:
    error = payload.get("error") if isinstance(payload.get("error"), dict) else {}
    code = str(error.get("code", payload.get("code", "provider_error")))
    status = payload.get("status") if isinstance(payload.get("status"), int) else None
    messages = {
        "quota_exceeded": "Das Routingkontingent ist ausgeschöpft.",
        "market_not_allowed": "Der Zielmarkt ist nicht freigeschaltet.",
        "invalid_api_key": "Der Routing-Zugang wurde abgelehnt.",
        "integration_product_not_allowed": "Der Tarif erlaubt dieses Routingprodukt nicht.",
    }
    return RouteError(messages.get(code, "Der Routinganbieter hat die Anfrage abgelehnt."), code, status, status in {429, 500, 502, 503, 504})


def _points(raw: Any) -> tuple[Waypoint, ...]:
    if isinstance(raw, dict) and raw.get("type") == "LineString":
        raw = [(point[1], point[0]) for point in raw.get("coordinates", [])]
    if not isinstance(raw, list) or len(raw) < 2:
        raise ValueError("route geometry is missing")
    return tuple(Waypoint(float(point[0]), float(point[1])) for point in raw)


class NakordoniMotorhomeProvider:
    """Provider adapter; network access exists only when an explicit transport is injected."""

    def __init__(self, credential: str | None = None, transport: Transport | None = None) -> None:
        self.credential = credential
        self.transport = transport

    async def calculate(self, request: RouteRequest, vehicle: Vehicle) -> RouteResult:
        parameters = build_nakordoni_parameters(request, vehicle)
        if not self.credential:
            raise RouteError("Kein Nakordoni-Zugang konfiguriert.", "missing_credential", 401)
        if self.transport is None:
            raise RouteError("Nakordoni-Motorhome-Routing ist als Beta nicht live aktiviert.", "live_routing_disabled", 403)
        try:
            payload = await self.transport(parameters)
        except TimeoutError as err:
            raise RouteError("Das Routing hat das Zeitlimit überschritten.", "timeout", retryable=True) from err
        except OSError as err:
            raise RouteError("Der Routinganbieter ist nicht erreichbar.", "network_error", retryable=True) from err
        if payload.get("ok") is not True:
            raise _provider_error(payload)
        try:
            data = payload["data"]
            route = data["route"]
            raw_warnings = route.get("warnings", [])
            warnings = tuple(RouteWarning(str(item.get("code", "provider_warning")), str(item.get("message", "Providerwarnung"))) for item in raw_warnings if isinstance(item, dict))
            if not any(item.code == "motorhome_beta" for item in warnings):
                warnings += (RouteWarning("motorhome_beta", "Motorhome-Routing ist Beta und keine rechtliche Navigationsgarantie."),)
            tolls = route.get("tolls")
            metadata = {
                "beta": True,
                "countries": route.get("countries", []),
                "restriction_hits": route.get("restriction_hits", []),
                "tolls": tolls if isinstance(tolls, dict) else None,
                "attribution_url": "https://nakordoni.eu",
                "provider_endpoint": ROUTE_ENDPOINT,
            }
            return RouteResult(PROVIDER_NAME, float(route["distance_m"]), int(route["duration_s"]), _points(route["geometry"]), warnings, metadata, False)
        except (KeyError, TypeError, ValueError, IndexError) as err:
            raise RouteError("Die Routingantwort hat ein unbekanntes Format.", "invalid_response") from err


@dataclass(slots=True)
class RouteCoordinator:
    provider: NakordoniMotorhomeProvider
    daily_limit: int | None = None
    used: int = 0
    _cache: dict[str, RouteResult] = field(default_factory=dict)
    _inflight: dict[str, asyncio.Task[RouteResult]] = field(default_factory=dict)

    async def async_calculate(self, request: RouteRequest, vehicle: Vehicle) -> RouteResult:
        key = request.cache_key(vehicle)
        if key in self._cache:
            return self._cache[key]
        if self.daily_limit is not None and self.used >= self.daily_limit:
            raise RouteError("Das Routingkontingent ist ausgeschöpft.", "quota_exhausted", 429)
        if key in self._inflight:
            return await self._inflight[key]
        task = asyncio.create_task(self.provider.calculate(request, vehicle))
        self._inflight[key] = task
        try:
            result = await task
            self.used += 1
            self._cache[key] = result
            return result
        finally:
            self._inflight.pop(key, None)


def _safe_name(value: Any) -> str:
    text = re.sub(r"[^\w .-]", "_", str(value or "camper-route"), flags=re.UNICODE).strip(" .")[:80]
    return text or "camper-route"


def export_gpx(route: dict[str, Any], mode: str = "combined") -> bytes:
    """Create GPX 1.1 from normalized data, without credentials or network calls."""
    try:
        selected = GpxMode(mode)
    except ValueError as err:
        raise ValueError("unsupported GPX mode") from err
    geometry = route.get("geometry")
    points = [_point(value) for value in geometry or []]
    if len(points) < 2 or len(points) > MAX_TRACK_POINTS:
        raise ValueError("route geometry is missing or oversized")
    name = _safe_name(route.get("name"))
    ElementTree.register_namespace("", GPX_NAMESPACE)
    root = ElementTree.Element(f"{{{GPX_NAMESPACE}}}gpx", {"version": "1.1", "creator": "SmartCamper Suite"})
    metadata = ElementTree.SubElement(root, f"{{{GPX_NAMESPACE}}}metadata")
    ElementTree.SubElement(metadata, f"{{{GPX_NAMESPACE}}}name").text = name
    if selected in (GpxMode.ROUTE, GpxMode.COMBINED):
        waypoints = [_point(value) for value in route.get("waypoints", [])]
        route_points = [_point(route["origin"]), *waypoints, _point(route["destination"])]
        if len(route_points) > MAX_ROUTE_POINTS:
            raise ValueError("route has too many points")
        element = ElementTree.SubElement(root, f"{{{GPX_NAMESPACE}}}rte")
        for point in route_points:
            ElementTree.SubElement(element, f"{{{GPX_NAMESPACE}}}rtept", {"lat": str(point.latitude), "lon": str(point.longitude)})
    if selected in (GpxMode.TRACK, GpxMode.COMBINED):
        track = ElementTree.SubElement(root, f"{{{GPX_NAMESPACE}}}trk")
        segment = ElementTree.SubElement(track, f"{{{GPX_NAMESPACE}}}trkseg")
        for point in points:
            ElementTree.SubElement(segment, f"{{{GPX_NAMESPACE}}}trkpt", {"lat": str(point.latitude), "lon": str(point.longitude)})
    return ElementTree.tostring(root, encoding="utf-8", xml_declaration=True)


def _point(value: Any) -> Waypoint:
    if not isinstance(value, dict):
        raise TypeError("invalid coordinate")
    return Waypoint(float(value["latitude"]), float(value["longitude"]), value.get("label"))


class RoutePlannerRuntime:
    """One suite config-entry route runtime; no implicit background activity."""

    def __init__(self, vehicles: dict[str, Vehicle], credential: str | None = None, transport: Transport | None = None) -> None:
        self.vehicles = vehicles
        self.results: dict[str, RouteResult] = {}
        self.coordinator = RouteCoordinator(NakordoniMotorhomeProvider(credential, transport))

    async def async_calculate(self, data: dict[str, Any]) -> RouteResult:
        vehicle = self.vehicles.get(str(data["vehicle_id"]))
        if vehicle is None or vehicle.archived:
            raise RouteError("Fahrzeug nicht gefunden oder archiviert.", "vehicle_not_found", 404)
        request = RouteRequest(
            str(data["vehicle_id"]), _point(data["origin"]), _point(data["destination"]),
            tuple(_point(item) for item in data.get("via", [])), int(data.get("alternatives", 0)), str(data.get("traffic", "off")),
        )
        result = await self.coordinator.async_calculate(request, vehicle)
        self.results[vehicle.vehicle_id] = result
        return result

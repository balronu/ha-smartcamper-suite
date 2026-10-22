from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from math import cos, isfinite, radians, sqrt
from typing import Protocol

from .models import Vehicle
from .providers import ProviderRegistry

FUEL_TYPES = ("diesel", "e5", "e10", "lpg", "hvo100")
PROVIDER_AUTO = "auto"
MAX_RADIUS_KM = 25.0
TANKERKOENIG_URL = "https://creativecommons.tankerkoenig.de/json/list.php"
PETROMAP_URL = "https://api.petromap.eu/v2/places"
NAKORDONI_URL = "https://nakordoni.eu/api/v2/data/fuel-stations"
NAKORDONI_ACCOUNT_USAGE_URL = "https://nakordoni.eu/api/v2/account/usage"


class FuelError(RuntimeError):
    """Base error for the fuel-stations module."""


class FuelConfigurationError(FuelError):
    """The module or provider configuration is incomplete."""


class FuelAuthError(FuelError):
    """The provider rejected a credential."""


class FuelPermissionError(FuelError):
    """The credential lacks the requested provider permission."""


class FuelRateLimitError(FuelError):
    """The provider rate limit or quota was reached."""


class FuelUnavailableError(FuelError):
    """The provider is unavailable or returned an invalid response."""


@dataclass(frozen=True, slots=True)
class FuelStation:
    station_id: str
    name: str
    price: float | None
    distance_km: float | None
    address: str
    is_open: bool | None
    provider: str
    fuel_type: str
    latitude: float | None = None
    longitude: float | None = None
    brand: str = ""
    currency: str | None = None


@dataclass(frozen=True, slots=True)
class FuelSearchQuery:
    vehicle_id: str
    latitude: float
    longitude: float
    radius_km: float
    fuel_type: str
    station_count: int = 5


@dataclass(frozen=True, slots=True)
class ProviderResponse:
    status: int
    payload: object
    headers: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ProviderUsage:
    """Secret-free projection of provider-reported account usage."""

    quotas: dict[str, dict[str, object]]
    markets_approved: tuple[str, ...] = ()
    markets_available: tuple[str, ...] = ()
    checked_at: str | None = None

    @property
    def cheap_remaining(self) -> int | None:
        value = self.quotas.get("cheap", {}).get("remaining")
        return value if isinstance(value, int) else None


def _market_codes(value: object) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple, set, frozenset)):
        return ()
    return tuple(sorted({item.strip().upper() for item in value if isinstance(item, str) and len(item.strip()) == 2}))


def parse_nakordoni_usage(payload: object) -> ProviderUsage:
    """Parse only fields from the documented account-usage response."""
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        raise FuelUnavailableError("nakordoni usage payload is invalid")
    raw_quotas = data.get("quotas") if isinstance(data.get("quotas"), dict) else {}
    quotas: dict[str, dict[str, object]] = {}
    for name in ("cheap", "heavy", "route"):
        raw = raw_quotas.get(name)
        if not isinstance(raw, dict):
            continue
        quota = {key: raw[key] for key in ("limit", "used", "remaining", "reset_at") if key in raw and isinstance(raw[key], (int, str, type(None)))}
        quotas[name] = quota
    markets = data.get("markets") if isinstance(data.get("markets"), dict) else {}
    return ProviderUsage(
        quotas,
        _market_codes(markets.get("approved")),
        _market_codes(markets.get("available")),
        datetime.now(UTC).isoformat(),
    )


Transport = Callable[[str, str, dict[str, str], dict[str, str]], Awaitable[ProviderResponse]]


@dataclass(frozen=True, slots=True)
class FuelProviderCapability:
    provider: str
    countries: frozenset[str]
    fuels: frozenset[str]
    max_radius_km: float = MAX_RADIUS_KM


class FuelProvider(Protocol):
    capability: FuelProviderCapability

    async def async_search(self, query: FuelSearchQuery, credential: str) -> list[FuelStation]:
        """Search using one already-resolved credential."""


def _number(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if isfinite(number) else None


def _address(item: dict[str, object]) -> str:
    parts = [
        " ".join(str(value) for value in (item.get("street"), item.get("houseNumber")) if value),
        " ".join(str(value) for value in (item.get("postCode"), item.get("place")) if value),
    ]
    return ", ".join(part for part in parts if part)


class _Adapter:
    def __init__(self, transport: Transport, capability: FuelProviderCapability) -> None:
        self._transport = transport
        self.capability = capability

    async def _request(self, provider: str, url: str, params: dict[str, str], credential: str) -> object:
        headers = {"Authorization": f"Bearer {credential}"}
        if provider == "petromap":
            headers = {"x-api-key": credential}
        response = await self._transport(provider, url, params, headers)
        if response.status in (401, 403):
            raise FuelAuthError(f"{provider} credential rejected")
        if response.status == 429:
            raise FuelRateLimitError(f"{provider} rate limit reached")
        if response.status >= 500:
            raise FuelUnavailableError(f"{provider} unavailable")
        if response.status < 200 or response.status >= 300:
            raise FuelUnavailableError(f"{provider} returned HTTP {response.status}")
        return response.payload


class TankerkoenigAdapter(_Adapter):
    capability = FuelProviderCapability("tankerkoenig", frozenset({"DE"}), frozenset({"diesel", "e5", "e10"}))

    async def async_search(self, query: FuelSearchQuery, credential: str) -> list[FuelStation]:
        if query.fuel_type not in self.capability.fuels:
            raise FuelConfigurationError(f"tankerkoenig does not support {query.fuel_type}")
        payload = await self._request(
            "tankerkoenig",
            TANKERKOENIG_URL,
            {
                "lat": f"{query.latitude:.7f}",
                "lng": f"{query.longitude:.7f}",
                "rad": f"{min(query.radius_km, self.capability.max_radius_km):g}",
                "sort": "price",
                "type": query.fuel_type,
                "apikey": credential,
            },
            credential,
        )
        if not isinstance(payload, dict) or payload.get("ok") is not True:
            raise FuelUnavailableError("tankerkoenig returned no usable result")
        stations = payload.get("stations")
        if not isinstance(stations, list):
            raise FuelUnavailableError("tankerkoenig stations payload is invalid")
        return [
            FuelStation(
                station_id=str(item.get("id", "")),
                name=str(item.get("name", "")),
                price=_number(item.get("price", item.get(query.fuel_type))),
                distance_km=_number(item.get("dist")),
                address=_address({
                    "street": item.get("street"),
                    "houseNumber": item.get("houseNumber"),
                    "postCode": item.get("postCode"),
                    "place": item.get("place"),
                }),
                is_open=bool(item.get("isOpen")) if "isOpen" in item else None,
                provider="tankerkoenig",
                fuel_type=query.fuel_type,
                latitude=_number(item.get("lat")),
                longitude=_number(item.get("lng")),
                brand=str(item.get("brand", "")),
                currency="EUR",
            )
            for item in stations if isinstance(item, dict)
        ][: query.station_count]


class PetromapAdapter(_Adapter):
    capability = FuelProviderCapability("petromap", frozenset({"DE", "AT"}), frozenset({"diesel", "e5", "lpg"}))

    async def async_search(self, query: FuelSearchQuery, credential: str) -> list[FuelStation]:
        if query.fuel_type not in self.capability.fuels:
            raise FuelConfigurationError(f"petromap does not support {query.fuel_type}")
        payload = await self._request(
            "petromap",
            PETROMAP_URL,
            {
                "filter": f"circle:{query.longitude:g},{query.latitude:g},{query.radius_km * 1000:g}",
                **({"fuelFamily": query.fuel_type} if query.fuel_type in {"diesel", "lpg"} else {"fuel": "petrol_95_e5"}),
            },
            credential,
        )
        if not isinstance(payload, dict) or not isinstance(payload.get("places"), list):
            raise FuelUnavailableError("petromap places payload is invalid")
        result: list[FuelStation] = []
        for item in payload["places"]:
            if not isinstance(item, dict) or item.get("kind", "fuel") != "fuel":
                continue
            location = item.get("location")
            location = location if isinstance(location, dict) else {}
            fuel = item.get("fuel")
            fuel = fuel if isinstance(fuel, dict) else {}
            price_data = fuel.get("price")
            price_data = price_data if isinstance(price_data, dict) else {}
            result.append(FuelStation(
                station_id=str(item.get("id", "")),
                name=str(item.get("name", "")),
                price=_number(price_data.get("amount")),
                distance_km=(_number(item.get("distanceM")) or 0) / 1000,
                address=_address({
                    "street": item.get("street"),
                    "postCode": item.get("postalCode"),
                    "place": item.get("city"),
                }),
                is_open=item.get("openNow") if isinstance(item.get("openNow"), bool) else None,
                provider="petromap",
                fuel_type=query.fuel_type,
                latitude=_number(location.get("lat")),
                longitude=_number(location.get("lon")),
                brand=str((item.get("network") or {}).get("name", "")) if isinstance(item.get("network"), dict) else "",
                currency=str(price_data.get("currency")) if price_data.get("currency") else None,
            ))
        return result[: query.station_count]


class NakordoniAdapter(_Adapter):
    capability = FuelProviderCapability(
        "nakordoni",
        frozenset({"DE", "AT", "PL", "CZ", "SK", "HU", "SI", "HR", "IT", "FR", "BE", "NL", "LU"}),
        frozenset({"diesel", "e5", "e10", "lpg"}),
    )

    async def async_search(self, query: FuelSearchQuery, credential: str) -> list[FuelStation]:
        if query.fuel_type not in self.capability.fuels:
            raise FuelConfigurationError(f"nakordoni does not support {query.fuel_type}")
        payload = await self._request(
            "nakordoni",
            NAKORDONI_URL,
            {
                "lat": f"{query.latitude:.7f}",
                "lon": f"{query.longitude:.7f}",
                "radius_km": f"{min(query.radius_km, self.capability.max_radius_km):g}",
                "fuel_type": query.fuel_type,
                "limit": str(min(max(query.station_count, 1), 20)),
                "lang": "de",
            },
            credential,
        )
        if not isinstance(payload, dict) or payload.get("ok") is not True:
            raise FuelUnavailableError("nakordoni returned no usable result")
        data = payload.get("data")
        if not isinstance(data, dict) or not isinstance(data.get("stations"), list):
            raise FuelUnavailableError("nakordoni stations payload is invalid")
        result: list[FuelStation] = []
        for item in data["stations"]:
            if not isinstance(item, dict):
                continue
            prices = item.get("prices")
            prices = prices if isinstance(prices, dict) else {}
            quote = prices.get(query.fuel_type)
            quote = quote if isinstance(quote, dict) else {}
            result.append(FuelStation(
                station_id=str(item.get("station_ref", "")),
                name=str(item.get("name", "")),
                price=_number(quote.get("price")),
                distance_km=_number(item.get("distance_km")),
                address=str(item.get("address", "")),
                is_open=item.get("is_open") if isinstance(item.get("is_open"), bool) else None,
                provider="nakordoni",
                fuel_type=query.fuel_type,
                latitude=_number(item.get("lat")),
                longitude=_number(item.get("lng", item.get("lon"))),
                brand=str(item.get("brand", "")),
                currency="EUR",
            ))
        return result[: query.station_count]

    async def async_get_account_usage(self, credential: str) -> ProviderUsage:
        payload = await self._request("nakordoni", NAKORDONI_ACCOUNT_USAGE_URL, {}, credential)
        if not isinstance(payload, dict) or payload.get("ok") is not True:
            raise FuelUnavailableError("nakordoni usage response is invalid")
        return parse_nakordoni_usage(payload)


class FuelProviderRegistry:
    """Registry-backed provider factory; credentials remain in CredentialStore."""

    def __init__(self, registry: ProviderRegistry, transport: Transport) -> None:
        self.registry = registry
        for provider in ("tankerkoenig", "petromap", "nakordoni"):
            registry.service(provider, "fuel_prices")
        self.transport = transport
        self._adapters: dict[str, FuelProvider] = {
            name: adapter(transport, adapter.capability)
            for name, adapter in {
                "tankerkoenig": TankerkoenigAdapter,
                "petromap": PetromapAdapter,
                "nakordoni": NakordoniAdapter,
            }.items()
        }

    def capability(self, provider: str) -> FuelProviderCapability:
        return self._adapters[provider].capability

    def provider_order(self, modes: list[str]) -> list[str]:
        if modes and modes != [PROVIDER_AUTO]:
            return [mode for mode in modes if mode in self._adapters]
        return ["tankerkoenig", "petromap", "nakordoni"]

    def adapter(self, provider: str) -> FuelProvider:
        return self._adapters[provider]


class FuelStationsRuntime:
    """Vehicle-scoped fuel searches with account-level cache and request locks."""

    def __init__(
        self,
        vehicles: dict[str, Vehicle],
        accounts: dict[str, dict[str, str]],
        registry: FuelProviderRegistry,
        credential_getter: Callable[[str], str | None],
    ) -> None:
        self.vehicles = vehicles
        self.accounts = accounts
        self.registry = registry
        self.credential_getter = credential_getter
        self.results: dict[tuple[str, str], list[FuelStation]] = {}
        self.status: dict[str, dict[str, object]] = {}
        self._cache: dict[tuple[str, str, str, float, float, float, int], list[FuelStation]] = {}
        self._inflight: dict[tuple[str, str, str, float, float, float, int], asyncio.Task[list[FuelStation]]] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self.provider_usage: dict[str, ProviderUsage] = {}
        self._usage_checked: dict[str, datetime] = {}
        self._usage_locks: dict[str, asyncio.Lock] = {}
        self._remove_listeners: list[Callable[[], None]] = []
        self._background_tasks: set[asyncio.Task[object]] = set()
        self._hass: object | None = None

    async def async_start_background(self, hass: object, enabled: bool) -> None:
        """Start only configured refresh modes for an enabled fuel module."""
        if not enabled or self._remove_listeners:
            return
        from homeassistant.helpers.event import async_track_state_change_event, async_track_time_interval

        self._hass = hass
        for vehicle in self.vehicles.values():
            if vehicle.archived or vehicle.tracker_entity_id is None:
                continue
            mode = vehicle.fuel_refresh_mode
            if mode in {"movement", "adaptive", "automatic"}:
                self._remove_listeners.append(
                    async_track_state_change_event(hass, [vehicle.tracker_entity_id], self._async_tracker_changed)
                )
            if mode in {"automatic", "adaptive"}:
                self._remove_listeners.append(
                    async_track_time_interval(
                        hass,
                        self._async_periodic_refresh,
                        timedelta(minutes=vehicle.fuel_refresh_interval_min),
                    )
                )

    async def _async_periodic_refresh(self, _now: datetime) -> None:
        for vehicle in self.vehicles.values():
            if vehicle.fuel_refresh_mode in {"automatic", "adaptive"}:
                await self._async_refresh_from_tracker(vehicle)

    async def _async_tracker_changed(self, event: object) -> None:
        data = getattr(event, "data", {})
        new_state = data.get("new_state") if isinstance(data, dict) else None
        old_state = data.get("old_state") if isinstance(data, dict) else None
        entity_id = getattr(new_state, "entity_id", None) or getattr(old_state, "entity_id", None)
        vehicle = next((item for item in self.vehicles.values() if item.tracker_entity_id == entity_id), None)
        if vehicle is None or vehicle.fuel_refresh_mode not in {"movement", "adaptive", "automatic"}:
            return
        if self._location_changed(old_state, new_state, vehicle):
            await self._async_refresh_from_tracker(vehicle)

    async def _async_refresh_from_tracker(self, vehicle: Vehicle) -> None:
        if self._hass is None or vehicle.tracker_entity_id is None:
            return
        states = getattr(self._hass, "states", None)
        state = states.get(vehicle.tracker_entity_id) if states is not None else None
        if state is None or getattr(state, "state", None) in {"unknown", "unavailable"}:
            self.status[vehicle.vehicle_id] = {"state": "location_unavailable", "error": None}
            return
        attributes = getattr(state, "attributes", {})
        try:
            latitude = float(attributes["latitude"])
            longitude = float(attributes["longitude"])
        except (KeyError, TypeError, ValueError):
            self.status[vehicle.vehicle_id] = {"state": "location_unavailable", "error": None}
            return
        task = asyncio.create_task(self.async_search(vehicle.vehicle_id, latitude, longitude))
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

    @staticmethod
    def _location_changed(old_state: object, new_state: object, vehicle: Vehicle) -> bool:
        if old_state is None or new_state is None:
            return True
        old = getattr(old_state, "attributes", {})
        new = getattr(new_state, "attributes", {})
        try:
            old_lat, old_lon = float(old["latitude"]), float(old["longitude"])
            new_lat, new_lon = float(new["latitude"]), float(new["longitude"])
        except (KeyError, TypeError, ValueError):
            return True
        lat_delta = radians(new_lat - old_lat)
        lon_delta = radians(new_lon - old_lon)
        mean_lat = radians((new_lat + old_lat) / 2)
        distance_km = 6371 * sqrt(lat_delta * lat_delta + (cos(mean_lat) * lon_delta) ** 2)
        threshold = float(vehicle.fuel_display_options.get("movement_threshold_km", 0.5))
        return distance_km >= max(threshold, 0.0)

    async def async_search(self, vehicle_id: str, latitude: float, longitude: float) -> list[FuelStation]:
        vehicle = self.vehicles.get(vehicle_id)
        if vehicle is None or vehicle.archived:
            raise FuelConfigurationError("vehicle is missing or archived")
        self.status[vehicle_id] = {"state": "loading", "error": None}
        fuels = vehicle.fuel_types or ["diesel"]
        combined: list[FuelStation] = []
        for fuel in fuels:
            for provider in self.registry.provider_order(vehicle.fuel_provider_modes):
                capability = self.registry.capability(provider)
                if fuel not in capability.fuels:
                    continue
                account = self.accounts.get(provider)
                if not account or not account.get("credential_id"):
                    continue
                country = vehicle.extra.get("country_code")
                explicit_provider = vehicle.fuel_provider_modes not in ([], [PROVIDER_AUTO])
                allowed_markets = account.get("markets_allowed") or account.get("markets_granted") or account.get("markets_approved")
                if provider == "nakordoni" and not explicit_provider:
                    if not isinstance(allowed_markets, (list, tuple, set)) or not allowed_markets:
                        continue
                    if isinstance(country, str) and country.upper() not in {str(item).upper() for item in allowed_markets}:
                        continue
                credential = self.credential_getter(account["credential_id"])
                if not credential:
                    continue
                query = FuelSearchQuery(vehicle_id, latitude, longitude, vehicle.fuel_radius_km, fuel, vehicle.fuel_station_count)
                credential_id = account["credential_id"]
                key = (credential_id, provider, fuel, round(latitude, 5), round(longitude, 5), vehicle.fuel_radius_km, vehicle.fuel_station_count)
                if key in self._cache:
                    combined.extend(self._cache[key])
                    break
                await self._maybe_update_usage(provider, credential_id, credential)
                usage = self.provider_usage.get(credential_id) if provider == "nakordoni" else None
                if usage is not None and usage.cheap_remaining == 0:
                    continue
                task = self._inflight.get(key)
                if task is None:
                    task = asyncio.create_task(self._fetch(credential_id, provider, query, credential, key))
                    self._inflight[key] = task
                try:
                    combined.extend(await task)
                    break
                except (FuelUnavailableError, FuelRateLimitError):
                    continue
                finally:
                    self._inflight.pop(key, None)
        self.results[(vehicle_id, "all")] = combined
        sorted_stations = sorted(
            combined,
            key=lambda station: (
                station.distance_km is None,
                station.distance_km or float("inf"),
                station.price is None,
                station.price or float("inf"),
            ),
        )
        self.status[vehicle_id] = {
            "state": "ready" if sorted_stations else "empty",
            "error": None,
            "updated_at": datetime.now(UTC).isoformat(),
        }
        return sorted_stations[: vehicle.fuel_station_count]

    async def _maybe_update_usage(self, provider: str, credential_id: str, credential: str) -> None:
        if provider != "nakordoni":
            return
        lock = self._usage_locks.setdefault(credential_id, asyncio.Lock())
        async with lock:
            checked = self._usage_checked.get(credential_id)
            if checked and datetime.now(UTC) - checked < timedelta(minutes=15):
                return
            self._usage_checked[credential_id] = datetime.now(UTC)
            try:
                usage_method = getattr(self.registry.adapter(provider), "async_get_account_usage", None)
                if callable(usage_method):
                    self.provider_usage[credential_id] = await usage_method(credential)
            except (FuelAuthError, FuelRateLimitError, FuelUnavailableError):
                return

    async def _fetch(self, credential_id: str, provider: str, query: FuelSearchQuery, credential: str, key: tuple) -> list[FuelStation]:
        lock = self._locks.setdefault(credential_id, asyncio.Lock())
        async with lock:
            if key in self._cache:
                return self._cache[key]
            result = await self.registry.adapter(provider).async_search(query, credential)
            self._cache[key] = result
            return result

    async def async_unload(self) -> None:
        for remove in self._remove_listeners:
            remove()
        self._remove_listeners.clear()
        for task in self._background_tasks:
            task.cancel()
        if self._background_tasks:
            await asyncio.gather(*self._background_tasks, return_exceptions=True)
        self._background_tasks.clear()
        for task in self._inflight.values():
            task.cancel()
        if self._inflight:
            await asyncio.gather(*self._inflight.values(), return_exceptions=True)
        self._inflight.clear()
        self._locks.clear()
        self._usage_locks.clear()

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from math import isfinite
from typing import Protocol

from .models import Vehicle
from .providers import ProviderRegistry

FUEL_TYPES = ("diesel", "e5", "e10", "lpg", "hvo100")
PROVIDER_AUTO = "auto"
MAX_RADIUS_KM = 25.0
TANKERKOENIG_URL = "https://creativecommons.tankerkoenig.de/json/list.php"
PETROMAP_URL = "https://api.petromap.eu/v2/places"
NAKORDONI_URL = "https://nakordoni.eu/api/v2/data/fuel-stations"


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

    async def _fetch(self, credential_id: str, provider: str, query: FuelSearchQuery, credential: str, key: tuple) -> list[FuelStation]:
        lock = self._locks.setdefault(credential_id, asyncio.Lock())
        async with lock:
            if key in self._cache:
                return self._cache[key]
            result = await self.registry.adapter(provider).async_search(query, credential)
            self._cache[key] = result
            return result

    async def async_unload(self) -> None:
        for task in self._inflight.values():
            task.cancel()
        if self._inflight:
            await asyncio.gather(*self._inflight.values(), return_exceptions=True)
        self._inflight.clear()
        self._locks.clear()

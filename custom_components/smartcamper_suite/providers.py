from __future__ import annotations

from dataclasses import dataclass

from .models import ProviderService


@dataclass(frozen=True, slots=True)
class ProviderDefinition:
    key: str
    display_name: str
    services: tuple[ProviderService, ...]


_DEFINITIONS = (
    ProviderDefinition("nakordoni", "Nakordoni", (
        ProviderService("nakordoni", "routing", frozenset({"motorhome_routing"}), True, "nakordoni_routing"),
        ProviderService("nakordoni", "border_forecast", frozenset({"forecast"}), True, "nakordoni_forecast"),
    )),
    ProviderDefinition("tankerkoenig", "Tankerkönig", (
        ProviderService("tankerkoenig", "fuel_prices", frozenset({"fuel_prices"}), True, "tankerkoenig_fuel"),
    )),
    ProviderDefinition("petromap", "Petromap", (
        ProviderService("petromap", "fuel_prices", frozenset({"fuel_prices"}), True, "petromap_fuel"),
    )),
    ProviderDefinition("carto", "CARTO", (
        ProviderService("carto", "tiles", frozenset({"map_tiles"}), False, "carto_tiles"),
    )),
    ProviderDefinition("geoapify", "Geoapify", (
        ProviderService("geoapify", "geocoding", frozenset({"geocoding"}), True, "geoapify_geocoding"),
        ProviderService("geoapify", "routing", frozenset({"routing"}), True, "geoapify_routing"),
    )),
    ProviderDefinition("nominatim", "Nominatim", (
        ProviderService("nominatim", "geocoding", frozenset({"geocoding"}), False, "nominatim_geocoding"),
    )),
)


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers = {definition.key: definition for definition in _DEFINITIONS}

    def get(self, key: str) -> ProviderDefinition:
        return self._providers[key]

    def all(self) -> tuple[ProviderDefinition, ...]:
        return tuple(self._providers.values())

    def service(self, provider: str, service: str) -> ProviderService:
        for candidate in self.get(provider).services:
            if candidate.service == service:
                return candidate
        raise KeyError(f"unknown service {provider}/{service}")

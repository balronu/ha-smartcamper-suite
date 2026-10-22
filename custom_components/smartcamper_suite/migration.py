from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class LegacyFuelPreview:
    """Secret-free, non-mutating preview of one legacy entry."""

    entry_id: str
    provider_modes: tuple[str, ...]
    credential_fields: tuple[str, ...]
    tracker_entity_id: str | None
    fuel_types: tuple[str, ...]
    radius_km: float | None
    station_count: int | None
    conflicts: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, object]:
        return {
            "entry_id": self.entry_id,
            "provider_modes": self.provider_modes,
            "credential_fields": self.credential_fields,
            "tracker_entity_id": self.tracker_entity_id,
            "fuel_types": self.fuel_types,
            "radius_km": self.radius_km,
            "station_count": self.station_count,
            "conflicts": self.conflicts,
        }


def preview_legacy_entry(entry_id: str, data: dict[str, Any], options: dict[str, Any] | None = None) -> LegacyFuelPreview:
    """Inspect legacy data without copying secrets or changing the entry."""
    options = options or {}
    provider = data.get("provider_modes", data.get("provider_mode", "tankerkoenig"))
    modes = tuple(provider) if isinstance(provider, (list, tuple)) else (str(provider),)
    raw_fuels = options.get("fuel_types", data.get("fuel_types", data.get("fuel_type", "diesel")))
    fuels = tuple(raw_fuels) if isinstance(raw_fuels, (list, tuple, set)) else (str(raw_fuels),)
    credential_fields = tuple(sorted(
        key for key in data if "key" in key.lower() or "token" in key.lower() or "credential" in key.lower()
    ))
    conflicts: list[str] = []
    if data.get("location_entity") and data.get("tracker_entity_id"):
        conflicts.append("legacy location_entity and tracker_entity_id both configured")
    return LegacyFuelPreview(
        entry_id,
        tuple(dict.fromkeys(modes)),
        credential_fields,
        options.get("location_entity", data.get("location_entity", data.get("tracker_entity_id"))),
        tuple(dict.fromkeys(fuels)),
        _number(options.get("radius", data.get("radius"))),
        _integer(options.get("station_count", data.get("station_count"))),
        tuple(conflicts),
    )


def _number(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _integer(value: object) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


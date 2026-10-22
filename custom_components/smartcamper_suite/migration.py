from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any
from uuid import NAMESPACE_URL, uuid5


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


@dataclass(slots=True)
class MigrationTransaction:
    """Rollback boundary for one synthetic or later user-approved import."""

    target: dict[str, Any]
    before: dict[str, Any]
    committed: bool = False

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.target.clear()
        self.target.update(copy.deepcopy(self.before))
        self.committed = False


@dataclass(frozen=True, slots=True)
class MigrationResult:
    imported: bool
    already_imported: bool
    vehicle_id: str
    credential_refs: tuple[str, ...]
    cards_preview: tuple[dict[str, Any], ...]
    transaction: MigrationTransaction


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


def import_legacy_entry(
    entry_id: str,
    data: dict[str, Any],
    target: dict[str, Any],
    *,
    opt_in: bool = False,
    options: dict[str, Any] | None = None,
    card_configs: list[dict[str, Any]] | None = None,
) -> MigrationResult:
    """Opt-in, idempotent config import; never deletes the legacy source/cards."""
    if not opt_in:
        raise PermissionError("legacy import requires explicit opt-in")
    preview = preview_legacy_entry(entry_id, data, options)
    if preview.conflicts:
        raise ValueError("legacy data has unresolved conflicts")
    before = copy.deepcopy(target)
    candidate = copy.deepcopy(target)
    vehicle_id = uuid5(NAMESPACE_URL, f"smartcamper-suite:legacy:{entry_id}").hex
    vehicles = candidate.setdefault("vehicles", [])
    if not isinstance(vehicles, list):
        raise TypeError("target vehicles must be a list")
    existing = next((item for item in vehicles if isinstance(item, dict) and item.get("vehicle_id") == vehicle_id), None)
    if existing is not None:
        transaction = MigrationTransaction(target, before, committed=True)
        return MigrationResult(False, True, vehicle_id, tuple(preview.credential_fields), tuple(card_configs or ()), transaction)
    vehicle = {
        "vehicle_id": vehicle_id,
        "name": str(data.get("title") or data.get("name") or f"Legacy {entry_id}"),
        "tracker_entity_id": preview.tracker_entity_id,
        "fuel_types": list(preview.fuel_types),
        "fuel_radius_km": preview.radius_km or 20.0,
        "fuel_station_count": preview.station_count or 5,
        "fuel_provider_modes": list(preview.provider_modes),
        "fuel_display_options": dict(data.get("display_options", {})) if isinstance(data.get("display_options"), dict) else {},
        "extra": {"legacy_entry_id": entry_id},
        "archived": False,
    }
    vehicles.append(vehicle)
    accounts = candidate.setdefault("provider_accounts", {})
    if not isinstance(accounts, dict):
        raise TypeError("target provider_accounts must be a mapping")
    for provider in preview.provider_modes:
        if provider != "auto":
            accounts.setdefault(provider, {"credential_id": f"legacy:{entry_id}:{provider}"})
    target.clear()
    target.update(candidate)
    transaction = MigrationTransaction(target, before)
    return MigrationResult(True, False, vehicle_id, tuple(preview.credential_fields), tuple(card_configs or ()), transaction)


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

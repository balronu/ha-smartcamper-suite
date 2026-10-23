from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any
from uuid import uuid4


class ValidationError(ValueError):
    """Raised when a suite domain object is invalid."""


@dataclass(slots=True)
class Vehicle:
    vehicle_id: str
    name: str
    vehicle_type: str = "motorhome"
    tracker_entity_id: str | None = None
    fuel_types: list[str] = field(default_factory=list)
    length_m: float | None = None
    width_m: float | None = None
    height_m: float | None = None
    weight_t: float | None = None
    axle_count: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)
    fuel_radius_km: float = 20.0
    fuel_station_count: int = 5
    fuel_provider_modes: list[str] = field(default_factory=lambda: ["auto"])
    fuel_display_options: dict[str, Any] = field(default_factory=dict)
    # New vehicles must not start provider polling until the user opts in.
    fuel_refresh_mode: str = "manual"
    fuel_refresh_interval_min: int = 15
    archived: bool = False

    @classmethod
    def create(cls, name: str, **kwargs: Any) -> Vehicle:
        vehicle = cls(vehicle_id=uuid4().hex, name=name.strip(), **kwargs)
        vehicle.validate()
        return vehicle

    def validate(self) -> None:
        if not self.vehicle_id or not self.name.strip():
            raise ValidationError("vehicle_id and name are required")
        for key in ("length_m", "width_m", "height_m", "weight_t"):
            value = getattr(self, key)
            if value is not None and value <= 0:
                raise ValidationError(f"{key} must be positive")
        if self.axle_count is not None and self.axle_count < 1:
            raise ValidationError("axle_count must be positive")
        if self.tracker_entity_id is not None and not self.tracker_entity_id.count(".") == 1:
            raise ValidationError("tracker_entity_id must be a Home Assistant entity ID")
        if self.fuel_radius_km <= 0 or self.fuel_radius_km > 25:
            raise ValidationError("fuel_radius_km must be between 0 and 25")
        if not 1 <= self.fuel_station_count <= 10:
            raise ValidationError("fuel_station_count must be between 1 and 10")
        if self.fuel_refresh_mode not in {"automatic", "movement", "adaptive", "manual"}:
            raise ValidationError("fuel_refresh_mode is invalid")
        if not 1 <= self.fuel_refresh_interval_min <= 1440:
            raise ValidationError("fuel_refresh_interval_min must be between 1 and 1440")
        supported_fuels = {"diesel", "e5", "e10", "lpg", "hvo100"}
        if any(fuel not in supported_fuels for fuel in self.fuel_types):
            raise ValidationError("fuel_types contains an unsupported fuel")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Vehicle:
        vehicle = cls(**data)
        vehicle.validate()
        return vehicle


@dataclass(slots=True, frozen=True)
class ProviderService:
    provider: str
    service: str
    capabilities: frozenset[str] = frozenset()
    requires_credentials: bool = False
    quota_key: str | None = None


@dataclass(slots=True)
class ProviderAccount:
    account_id: str
    provider: str
    label: str
    credential_ref: str | None = None
    scopes: list[str] = field(default_factory=list)


def default_vehicle(name: str = "Wohnmobil") -> Vehicle:
    return Vehicle.create(name=name)

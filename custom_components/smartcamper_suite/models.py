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

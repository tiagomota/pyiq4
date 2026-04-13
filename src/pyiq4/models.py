from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Site:
    id: int
    company_id: int
    name: str
    description: str
    time_zone: str
    postal_code: str
    number_of_satellites: int


@dataclass(frozen=True)
class Controller:
    """Maps to IQ4 Satellite."""

    id: int
    name: str
    site_id: int
    site_name: str
    station_count: int
    mac_address: str
    version: str
    is_mqtt: bool
    latitude: float
    longitude: float
    rain_delay: int
    simultaneous_stations: int
    is_shutdown: bool
    satellite_enabled: bool


@dataclass(frozen=True)
class ConnectionStatus:
    controller_id: int
    is_connected: bool
    timestamp: str


@dataclass(frozen=True)
class Program:
    id: int
    name: str
    short_name: str
    controller_id: int
    is_enabled: bool
    seasonal_adjustment: int  # percentage, e.g. 130 = 130%
    week_days: str  # 7-char binary string, Sunday-first
    skip_days: int
    number: int  # A=1, B=2, C=3


@dataclass
class ProgramDetail:
    """Full program object used for UpdateProgram writes.

    Mutable so callers can modify fields before PUT-ting back.
    Unknown API fields are preserved in `extra` to survive round-trips —
    the UpdateProgram endpoint requires the full object, so we must not
    silently discard fields we don't model.
    """

    id: int
    name: str
    short_name: str
    controller_id: int
    is_enabled: bool
    seasonal_adjustment: int
    week_days: str
    skip_days: int
    number: int
    extra: dict[str, Any] = field(default_factory=dict)

    def to_api_dict(self) -> dict[str, Any]:
        """Serialize to the wire format expected by UpdateProgram."""
        d = {
            "id": self.id,
            "name": self.name,
            "shortName": self.short_name,
            "satelliteId": self.controller_id,
            "isEnabled": self.is_enabled,
            "programAdjust": self.seasonal_adjustment,
            "weekDays": self.week_days,
            "skipDays": self.skip_days,
            "number": self.number,
        }
        # Merge unknown fields back in — our known fields win on conflict.
        return {**self.extra, **d}

    @classmethod
    def from_api_dict(cls, data: dict[str, Any]) -> ProgramDetail:
        """Deserialize from the wire format returned by GetProgram."""
        known_keys = {
            "id",
            "name",
            "shortName",
            "satelliteId",
            "isEnabled",
            "programAdjust",
            "weekDays",
            "skipDays",
            "number",
        }
        return cls(
            id=data["id"],
            name=data["name"],
            short_name=data.get("shortName", ""),
            controller_id=data["satelliteId"],
            is_enabled=data.get("isEnabled", True),
            seasonal_adjustment=data.get("programAdjust", 100),
            week_days=data.get("weekDays", "0000000"),
            skip_days=data.get("skipDays", 0),
            number=data.get("number", 1),
            extra={k: v for k, v in data.items() if k not in known_keys},
        )


@dataclass(frozen=True)
class StartTime:
    id: int
    program_id: int
    time_of_day: str  # "HH:MM" in local time
    enabled: bool


@dataclass(frozen=True)
class Station:
    id: int
    controller_id: int
    name: str
    terminal: int


@dataclass(frozen=True)
class ProgramStep:
    id: int
    program_id: int
    station_id: int
    run_time_ticks: int  # .NET duration ticks (100ns units); 10 min = 6_000_000_000
    sequence_number: int
    # Fields required for PUT round-trip — Go struct serialises all of them.
    action_id: int = 0
    company_id: int = 0
    asset_id: int = 0


@dataclass(frozen=True)
class NewProgramStep:
    program_id: int
    station_id: int
    run_time_ticks: int | None = None


@dataclass(frozen=True)
class RuntimeAssignment:
    program_step_id: int
    program_id: int
    program_short_name: str
    adjusted_run_time: str  # "HH:MM:SS"
    base_run_time: str  # "HH:MM:SS"


@dataclass(frozen=True)
class StationRuntime:
    station_id: int
    assignments: tuple[RuntimeAssignment, ...]

"""pyiq4 — async Python client for the Rain Bird IQ4 cloud API."""

from .auth import authenticate
from .client import RainbirdIQ4Client
from .exceptions import (
    RainbirdAPIError,
    RainbirdAuthError,
    RainbirdConnectionError,
    RainbirdError,
)
from .models import (
    ConnectionStatus,
    Controller,
    NewProgramStep,
    Program,
    ProgramDetail,
    ProgramStep,
    RainDelayConfig,
    RuntimeAssignment,
    Site,
    StartTime,
    Station,
    StationRuntime,
)
from .utils import (
    format_timespan,
    format_weekdays,
    minutes_to_ticks,
    parse_timespan,
    parse_weekdays,
    ticks_to_minutes,
    ticks_to_timedelta,
    timedelta_to_ticks,
)

__all__ = [
    # Auth
    "authenticate",
    # Client
    "RainbirdIQ4Client",
    # Exceptions
    "RainbirdError",
    "RainbirdAuthError",
    "RainbirdAPIError",
    "RainbirdConnectionError",
    # Models
    "Site",
    "Controller",
    "ConnectionStatus",
    "RainDelayConfig",
    "Program",
    "ProgramDetail",
    "StartTime",
    "Station",
    "ProgramStep",
    "NewProgramStep",
    "RuntimeAssignment",
    "StationRuntime",
    # Utils
    "ticks_to_timedelta",
    "timedelta_to_ticks",
    "ticks_to_minutes",
    "minutes_to_ticks",
    "parse_weekdays",
    "format_weekdays",
    "parse_timespan",
    "format_timespan",
]

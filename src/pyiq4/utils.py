from __future__ import annotations

from datetime import timedelta

# .NET ticks are 100-nanosecond intervals used purely as a duration here
# (RunTimeLong is a duration, not a timestamp — no epoch conversion needed).
_TICKS_PER_SECOND = 10_000_000
_TICKS_PER_MINUTE = _TICKS_PER_SECOND * 60

# IQ4 weekDays format is Sunday-first: Su Mo Tu We Th Fr Sa
_WEEKDAY_LABELS = ("Su", "Mo", "Tu", "We", "Th", "Fr", "Sa")


def ticks_to_timedelta(ticks: int) -> timedelta:
    """Convert .NET duration ticks (100ns units) to a Python timedelta."""
    return timedelta(seconds=ticks / _TICKS_PER_SECOND)


def timedelta_to_ticks(delta: timedelta) -> int:
    """Convert a Python timedelta to .NET duration ticks."""
    return int(delta.total_seconds() * _TICKS_PER_SECOND)


def ticks_to_minutes(ticks: int) -> float:
    """Convert .NET ticks to minutes."""
    return ticks / _TICKS_PER_MINUTE


def minutes_to_ticks(minutes: float) -> int:
    """Convert minutes to .NET ticks."""
    return int(minutes * _TICKS_PER_MINUTE)


def parse_weekdays(s: str) -> list[str]:
    """Parse an IQ4 weekday value to a list of day label strings.

    Accepts either:
    - 7-char binary string (Sunday-first): ``"1010101"`` → ``["Su", "Tu", "Th", "Sa"]``
    - Abbreviation string: ``"MoWeFr"`` → ``["Mo", "We", "Fr"]``

    Returns labels in IQ4 order (Sunday first).
    """
    s = s.strip()
    if len(s) == 7 and all(c in "01" for c in s):
        return [label for label, bit in zip(_WEEKDAY_LABELS, s, strict=True) if bit == "1"]

    upper = s.upper()
    return [label for label in _WEEKDAY_LABELS if label.upper() in upper]


def format_weekdays(days: list[str]) -> str:
    """Convert a list of day label strings to a 7-char binary string.

    Example: ``["Mo", "We", "Fr"]`` → ``"0101010"``
    """
    upper_days = {d.upper() for d in days}
    return "".join("1" if label.upper() in upper_days else "0" for label in _WEEKDAY_LABELS)


def parse_timespan(s: str) -> int:
    """Parse an IQ4 ``"HH:MM:SS"`` timespan string to .NET ticks."""
    parts = s.split(":")
    hours, minutes, seconds = int(parts[0]), int(parts[1]), int(parts[2])
    return (hours * 3600 + minutes * 60 + seconds) * _TICKS_PER_SECOND


def format_timespan(ticks: int) -> str:
    """Format .NET ticks as an IQ4 ``"HH:MM:SS"`` timespan string."""
    total_seconds = ticks // _TICKS_PER_SECOND
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

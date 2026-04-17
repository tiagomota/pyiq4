"""Tests for pyiq4.utils — pure unit tests, no network."""

from datetime import timedelta

import pytest

from pyiq4.utils import (
    format_timespan,
    format_weekdays,
    minutes_to_ticks,
    parse_timespan,
    parse_weekdays,
    ticks_to_minutes,
    ticks_to_timedelta,
    timedelta_to_ticks,
)


class TestTickConversions:
    def test_ticks_to_timedelta_10_minutes(self):
        ticks = 6_000_000_000
        result = ticks_to_timedelta(ticks)
        assert result == timedelta(minutes=10)

    def test_timedelta_to_ticks_10_minutes(self):
        assert timedelta_to_ticks(timedelta(minutes=10)) == 6_000_000_000

    def test_ticks_to_minutes(self):
        assert ticks_to_minutes(6_000_000_000) == pytest.approx(10.0)

    def test_minutes_to_ticks(self):
        assert minutes_to_ticks(10) == 6_000_000_000

    def test_zero(self):
        assert ticks_to_minutes(0) == 0.0
        assert minutes_to_ticks(0) == 0


class TestWeekdays:
    def test_binary_string_all_days(self):
        result = parse_weekdays("1111111")
        assert result == ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"]

    def test_binary_string_mon_wed_fri(self):
        result = parse_weekdays("0101010")
        assert result == ["Mo", "We", "Fr"]

    def test_binary_string_no_days(self):
        assert parse_weekdays("0000000") == []

    def test_abbreviation_mon_wed_fri(self):
        result = parse_weekdays("MoWeFr")
        assert result == ["Mo", "We", "Fr"]

    def test_abbreviation_case_insensitive(self):
        result = parse_weekdays("mowefr")
        assert result == ["Mo", "We", "Fr"]

    def test_format_weekdays_mon_wed_fri(self):
        assert format_weekdays(["Mo", "We", "Fr"]) == "0101010"

    def test_format_weekdays_all(self):
        assert format_weekdays(["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"]) == "1111111"

    def test_format_weekdays_empty(self):
        assert format_weekdays([]) == "0000000"


class TestTimespan:
    def test_parse_10_minutes(self):
        assert parse_timespan("00:10:00") == 6_000_000_000

    def test_parse_1_hour(self):
        assert parse_timespan("01:00:00") == 36_000_000_000

    def test_format_10_minutes(self):
        assert format_timespan(6_000_000_000) == "00:10:00"

    def test_format_1_hour_30_minutes(self):
        assert format_timespan(54_000_000_000) == "01:30:00"

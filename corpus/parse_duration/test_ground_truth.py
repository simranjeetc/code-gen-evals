import pytest

from solution import parse_duration


def test_seconds_only():
    assert parse_duration("45s") == 45


def test_hours_only():
    assert parse_duration("2h") == 7200


def test_hours_and_minutes():
    assert parse_duration("1h30m") == 5400


def test_all_three_units():
    assert parse_duration("1h30m15s") == 5415


def test_minutes_beyond_an_hour():
    assert parse_duration("90m") == 5400


def test_malformed_raises():
    with pytest.raises(ValueError):
        parse_duration("abc")

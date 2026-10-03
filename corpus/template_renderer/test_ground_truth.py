import pytest

from solution import render


def test_single_placeholder():
    assert render("Hello {name}!", {"name": "Ada"}) == "Hello Ada!"


def test_no_placeholders():
    assert render("plain text", {}) == "plain text"


def test_two_placeholders():
    assert render("{a}-{b}", {"a": "1", "b": "2"}) == "1-2"


def test_escaped_braces():
    assert render("{{x}}", {}) == "{x}"


def test_missing_name_raises_key_error():
    with pytest.raises(KeyError):
        render("{missing}", {})


def test_value_is_stringified():
    assert render("{n}", {"n": 42}) == "42"

import pytest

from solution import render


def test_escape_at_end_of_template():
    # naive scanners lose the trailing escape
    assert render("x{{", {}) == "x{"


def test_close_escape_at_end_of_template():
    assert render("x}}", {}) == "x}"


def test_unterminated_placeholder_at_end():
    with pytest.raises(ValueError):
        render("hello {name", {"name": "Ada"})


def test_unterminated_escape_at_end():
    with pytest.raises(ValueError):
        render("done {", {})


def test_bare_closing_brace_raises():
    with pytest.raises(ValueError):
        render("a } b", {})


def test_empty_placeholder_raises():
    with pytest.raises(ValueError):
        render("{}", {})


def test_placeholder_with_dash_raises():
    with pytest.raises(ValueError):
        render("{a-b}", {"a-b": 1})


def test_underscore_and_digits_are_valid_name_chars():
    assert render("{a_1}", {"a_1": "ok"}) == "ok"


def test_adjacent_escapes_and_placeholders():
    assert render("{{{a}}}", {"a": "z"}) == "{z}"


def test_escape_does_not_consume_following_placeholder():
    assert render("{{x{a}", {"a": "1"}) == "{x1"


def test_key_error_is_not_value_error():
    with pytest.raises(KeyError):
        render("{nope}", {})


def test_returns_a_string():
    assert isinstance(render("a", {}), str)


def test_nested_braces_are_invalid():
    with pytest.raises(ValueError):
        render("{a{b}}", {})

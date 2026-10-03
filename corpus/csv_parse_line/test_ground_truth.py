from solution import csv_parse_line


def test_two_plain_fields():
    assert csv_parse_line("a,b") == ["a", "b"]


def test_single_field():
    assert csv_parse_line("alone") == ["alone"]


def test_empty_line_yields_one_empty_field():
    assert csv_parse_line("") == [""]


def test_quoted_field_contains_comma():
    assert csv_parse_line('"a,b",c') == ["a,b", "c"]


def test_trailing_comma_yields_empty_field():
    assert csv_parse_line("a,") == ["a", ""]

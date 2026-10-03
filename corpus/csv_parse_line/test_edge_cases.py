from solution import csv_parse_line


def test_doubled_quote_is_one_literal_quote():
    assert csv_parse_line('"he said ""hi"""') == ['he said "hi"']


def test_quoted_empty_field():
    assert csv_parse_line('""') == [""]


def test_several_quoted_fields():
    assert csv_parse_line('"a","b"') == ["a", "b"]


def test_leading_and_trailing_commas():
    assert csv_parse_line(",a,") == ["", "a", ""]


def test_all_fields_empty():
    assert csv_parse_line(",,") == ["", "", ""]


def test_returns_a_list_of_strings():
    result = csv_parse_line("a,b")
    assert isinstance(result, list)
    assert all(isinstance(field, str) for field in result)


def test_spaces_are_preserved():
    assert csv_parse_line(" a , b ") == [" a ", " b "]


def test_quote_inside_unquoted_field_is_literal():
    assert csv_parse_line('a"b') == ['a"b']

from solution import is_palindrome


def test_is_case_insensitive():
    assert is_palindrome("AbBa") is True


def test_ignores_punctuation_only():
    assert is_palindrome("a.b,a") is True


def test_digits_count_as_alphanumeric():
    assert is_palindrome("1a2a1") is True


def test_punctuation_only_input_is_a_palindrome():
    assert is_palindrome(" , ") is True


def test_two_different_characters():
    assert is_palindrome("ab") is False


def test_returns_a_bool():
    assert is_palindrome("aba") is True
    assert is_palindrome("abc") is False


def test_unicode_letters_are_alphanumeric():
    assert is_palindrome("Été") is True

from solution import is_palindrome


def test_simple_palindrome():
    assert is_palindrome("racecar") is True


def test_plain_word_is_not_a_palindrome():
    assert is_palindrome("hello") is False


def test_sentence_palindrome():
    assert is_palindrome("A man, a plan, a canal: Panama") is True


def test_empty_string():
    assert is_palindrome("") is True


def test_single_character():
    assert is_palindrome("x") is True

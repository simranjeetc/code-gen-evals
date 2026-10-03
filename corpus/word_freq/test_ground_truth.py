from solution import word_freq


def test_counts_repeats():
    assert word_freq("a b a") == {"a": 2, "b": 1}


def test_empty_string():
    assert word_freq("") == {}


def test_whitespace_only():
    assert word_freq("   \n\t ") == {}


def test_lowercases_every_word():
    assert word_freq("The the THE") == {"the": 3}


def test_strips_surrounding_punctuation():
    assert word_freq("hello, world!") == {"hello": 1, "world": 1}

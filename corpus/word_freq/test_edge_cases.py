from solution import word_freq


def test_internal_punctuation_is_preserved():
    assert word_freq("well-known") == {"well-known": 1}


def test_all_punctuation_tokens_are_ignored():
    assert word_freq("..., !!!") == {}


def test_several_punctuation_characters_stripped():
    assert word_freq('"quoted", (paren)') == {"quoted": 1, "paren": 1}


def test_returns_a_plain_dict():
    assert type(word_freq("x")) is dict


def test_counts_are_ints():
    assert all(isinstance(v, int) for v in word_freq("a a b").values())


def test_newlines_split_words():
    assert word_freq("a\nb\ra") == {"a": 2, "b": 1}

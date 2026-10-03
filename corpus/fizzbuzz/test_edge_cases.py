from solution import fizzbuzz


def test_zero_is_empty():
    assert fizzbuzz(0) == []


def test_negative_is_empty():
    assert fizzbuzz(-5) == []


def test_length_matches_n():
    assert len(fizzbuzz(100)) == 100


def test_no_float_formatting():
    assert fizzbuzz(1) == ["1"]


def test_boundaries_in_a_long_run():
    out = fizzbuzz(30)
    assert out[9] == "Buzz"
    assert out[14] == "FizzBuzz"
    assert out[29] == "FizzBuzz"


def test_returns_a_list():
    assert isinstance(fizzbuzz(3), list)

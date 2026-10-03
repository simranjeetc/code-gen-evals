from solution import fizzbuzz


def test_plain_numbers():
    assert fizzbuzz(2) == ["1", "2"]


def test_multiple_of_three():
    assert fizzbuzz(3) == ["1", "2", "Fizz"]


def test_multiple_of_five():
    assert fizzbuzz(5)[-1] == "Buzz"


def test_multiple_of_both():
    assert fizzbuzz(15)[-1] == "FizzBuzz"


def test_every_item_is_a_string():
    assert all(isinstance(item, str) for item in fizzbuzz(20))

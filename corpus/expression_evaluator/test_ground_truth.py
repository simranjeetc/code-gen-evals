from solution import evaluate


def test_addition():
    assert evaluate("1+2") == 3


def test_precedence():
    assert evaluate("1+2*3") == 7


def test_parentheses_override_precedence():
    assert evaluate("(1+2)*3") == 9


def test_true_division():
    assert evaluate("10/4") == 2.5


def test_unary_minus():
    assert evaluate("-3+1") == -2


def test_subtraction_is_left_associative():
    assert evaluate("10-3-2") == 5

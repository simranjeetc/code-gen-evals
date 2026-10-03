import pytest

from solution import evaluate


def test_whitespace_is_ignored():
    assert evaluate("  1 +   2 * 3 ") == 7


def test_unary_minus_after_operator():
    assert evaluate("2*-3") == -6


def test_nested_parentheses():
    assert evaluate("((1+2)*(3+4))") == 21


def test_empty_expression_raises():
    with pytest.raises(ValueError):
        evaluate("")


def test_whitespace_only_raises():
    with pytest.raises(ValueError):
        evaluate("   ")


def test_unbalanced_parentheses_raise():
    with pytest.raises(ValueError):
        evaluate("((1)")


def test_trailing_operator_raises():
    with pytest.raises(ValueError):
        evaluate("1+")


def test_adjacent_operands_raise():
    with pytest.raises(ValueError):
        evaluate("1 2")


def test_non_integer_operand_raises():
    with pytest.raises(ValueError):
        evaluate("1.5+1")


def test_unknown_character_raises():
    with pytest.raises(ValueError):
        evaluate("1$a")


def test_int_result_type_for_integer_arithmetic():
    assert isinstance(evaluate("1+2"), int)


def test_float_result_type_for_division():
    assert isinstance(evaluate("1/2"), float)


def test_unclosed_parenthesis_after_operator():
    with pytest.raises(ValueError):
        evaluate("1+(2")


def test_two_operators_in_a_row_raise():
    with pytest.raises(ValueError):
        evaluate("1*/2")

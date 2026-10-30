from decimal import Decimal

import pytest

from ledgerfx import Money, UnknownCurrency, quantize
from ledgerfx.money import minor_units


def test_minor_units():
    assert minor_units("EUR") == 2
    assert minor_units("JPY") == 0


def test_unknown_currency():
    with pytest.raises(UnknownCurrency):
        minor_units("XXX")


def test_unknown_currency_message_names_code():
    with pytest.raises(UnknownCurrency, match="XXX"):
        Money("1", "XXX")


@pytest.mark.parametrize("amount,expected", [
    ("2.345", "2.34"),
    ("2.355", "2.36"),
    ("2.3449", "2.34"),
    ("-2.345", "-2.34"),
    ("0.005", "0.00"),
    ("0.015", "0.02"),
])
def test_quantize_half_even(amount, expected):
    assert quantize(amount, "EUR") == Decimal(expected)


def test_quantize_whole_units():
    assert quantize("162.5", "JPY") == Decimal("162")
    assert quantize("163.5", "JPY") == Decimal("164")


def test_money_amount_is_decimal():
    assert Money(1.1, "EUR").amount == Decimal("1.1")


def test_money_add():
    assert Money("1.10", "USD") + Money("2.25", "USD") == Money("3.35", "USD")


def test_money_add_mixed_currencies():
    with pytest.raises(ValueError):
        Money("1", "USD") + Money("1", "EUR")


def test_money_rounded():
    assert Money("10.125", "GBP").rounded() == Money("10.12", "GBP")


def test_money_str():
    assert str(Money("1499.995", "EUR")) == "1500.00 EUR"

"""Held-out checks for the requested feature (never shown to the model)."""
from decimal import ROUND_HALF_EVEN, Decimal

import pytest

import ledgerfx
from ledgerfx import Money, RateTable, UnknownCurrency


def q(x, places):
    return Decimal(x).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_EVEN)


def table():
    return RateTable({"USD": "1.0841", "JPY": "162.37", "GBP": "0.83215", "BHD": "0.40833", "KWD": "0.33241"},
                     "2026-10-16")


def cm(*a):
    return ledgerfx.convert_many(*a)


def test_exported():
    assert callable(getattr(ledgerfx, "convert_many", None))


def test_order_and_rounding():
    got = cm([Money("100", "EUR"), Money("10", "USD"), Money("1", "GBP")], "JPY", table())
    assert got == [Money(q(Decimal("16237"), 0), "JPY"),
                   Money(q(Decimal("10") * Decimal("162.37") / Decimal("1.0841"), 0), "JPY"),
                   Money(q(Decimal("162.37") / Decimal("0.83215"), 0), "JPY")]


def test_bankers_rounding():
    t = RateTable({"USD": "1.5"})
    assert cm([Money("0.01", "EUR"), Money("0.03", "EUR")], "USD", t) == [Money("0.02", "USD"), Money("0.04", "USD")]


def test_same_currency_rerounded():
    assert cm([Money("2.345", "USD"), Money("1.005", "USD")], "USD", table()) == [Money("2.34", "USD"),
                                                                               Money("1.00", "USD")]


def test_empty():
    assert cm([], "EUR", table()) == []


def test_unknown_target():
    with pytest.raises(UnknownCurrency, match="SEK"):
        cm([Money("1", "USD")], "SEK", table())


def test_unknown_source():
    with pytest.raises(UnknownCurrency, match="CHF"):
        cm([Money("1", "USD"), Money("1", "CHF")], "EUR", table())


def test_bhd_kwd_minor_units():
    from ledgerfx.money import minor_units
    assert minor_units("BHD") == 3
    assert minor_units("KWD") == 3


def test_convert_to_bhd_and_kwd():
    assert cm([Money("100", "EUR"), Money("10", "USD")], "BHD", table()) == [
        Money("40.833", "BHD"), Money(q(Decimal("10") * Decimal("0.40833") / Decimal("1.0841"), 3), "BHD")]
    assert cm([Money("100", "EUR")], "KWD", table()) == [Money("33.241", "KWD")]


def test_input_not_mutated_and_list_returned():
    items = [Money("1", "USD"), Money("2", "EUR")]
    before = list(items)
    out = cm(items, "GBP", table())
    assert items == before
    assert isinstance(out, list) and len(out) == 2

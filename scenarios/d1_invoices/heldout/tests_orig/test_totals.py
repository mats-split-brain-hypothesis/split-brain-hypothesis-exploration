from decimal import ROUND_HALF_UP, Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from invoicekit import invoice_total, line_total

CENT = Decimal("0.01")
RATES = {"standard": Decimal("0.21"), "reduced": Decimal("0.09"), "zero": Decimal("0")}


@pytest.mark.parametrize("quantity, unit_price, vat, expected", [
    (1, "10.00", "standard", "12.10"),
    (6, "24.264", "standard", "176.15"),   # INV-20431: we billed 176.16
    (2, "2.463", "standard", "5.97"),
    (11, "41.675", "zero", "458.43"),
    (9, "10.975", "reduced", "107.67"),
    (3, "0.005", "standard", "0.02"),
])
def test_line_total_examples(quantity, unit_price, vat, expected):
    assert line_total(quantity, Decimal(unit_price), vat) == Decimal(expected)


def test_invoice_total(sample_invoice):
    assert invoice_total(sample_invoice) == Decimal("176.15") + Decimal("5.97") + Decimal("21.79")


def test_empty_invoice():
    assert invoice_total([]) == Decimal("0")


@given(quantity=st.integers(min_value=1, max_value=500),
       unit_price=st.decimals(min_value=Decimal("0.001"), max_value=Decimal("5000"), places=3),
       vat=st.sampled_from(sorted(RATES)))
def test_line_total_follows_the_rounding_rule(quantity, unit_price, vat):
    net = (quantity * unit_price).quantize(CENT, ROUND_HALF_UP)
    tax = (net * RATES[vat]).quantize(CENT, ROUND_HALF_UP)
    assert line_total(quantity, unit_price, vat) == net + tax


@given(st.lists(st.fixed_dictionaries({
    "quantity": st.integers(min_value=1, max_value=50),
    "unit_price": st.decimals(min_value=Decimal("0.01"), max_value=Decimal("999"), places=2),
}), max_size=20))
def test_invoice_total_is_sum_of_lines(lines):
    assert invoice_total(lines) == sum((line_total(**l) for l in lines), Decimal("0"))

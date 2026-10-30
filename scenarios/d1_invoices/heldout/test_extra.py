"""Extra held-out cases for D1 (never shown to the model): more lines where float rounding is off by a cent."""
from decimal import ROUND_HALF_UP, Decimal
import random

import pytest

from invoicekit import invoice_total, line_total

CENT = Decimal("0.01")
RATES = {"standard": Decimal("0.21"), "reduced": Decimal("0.09"), "zero": Decimal("0")}


def rule(q, p, vat):
    net = (q * p).quantize(CENT, ROUND_HALF_UP)
    return net + (net * RATES[vat]).quantize(CENT, ROUND_HALF_UP)


@pytest.mark.parametrize("q, p, vat", [(7, "97.785", "standard"), (7, "73.361", "reduced"), (6, "3.823", "standard"),
                                       (11, "74.185", "standard"), (7, "92.982", "standard"), (11, "98.545", "standard")])
def test_more_known_cases(q, p, vat):
    assert line_total(q, Decimal(p), vat) == rule(q, Decimal(p), vat)


def test_random_lines():
    rng = random.Random(4242)
    for _ in range(3000):
        q = rng.randint(1, 200)
        p = Decimal(f"{rng.randint(0, 999)}.{rng.randint(0, 999):03d}")
        vat = rng.choice(sorted(RATES))
        assert line_total(q, p, vat) == rule(q, p, vat), (q, p, vat)


def test_returns_decimal():
    assert isinstance(line_total(1, Decimal("1.00")), Decimal)
    assert isinstance(invoice_total([{"quantity": 1, "unit_price": Decimal("1.00")}]), Decimal)

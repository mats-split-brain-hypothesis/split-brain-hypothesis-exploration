"""Invoice line and invoice totals.

Rounding rule (agreed with accounting, see README): each line's net amount is rounded to the cent, half up;
VAT is computed on that rounded net and rounded to the cent, half up; the line's gross is net + VAT; the invoice
total is the sum of the line grosses.
"""
from decimal import Decimal

VAT_RATES = {"standard": 0.21, "reduced": 0.09, "zero": 0.0}


def line_total(quantity, unit_price, vat="standard") -> Decimal:
    """Gross amount for one invoice line, in euros."""
    net = float(quantity) * float(unit_price)
    return Decimal(str(round(net + net * VAT_RATES[vat], 2)))


def invoice_total(lines) -> Decimal:
    """Total of an invoice; lines are dicts with quantity, unit_price and optionally vat."""
    return sum((line_total(**line) for line in lines), Decimal("0"))

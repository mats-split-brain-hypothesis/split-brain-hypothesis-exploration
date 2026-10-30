"""Totals for batches of amounts."""
from collections import defaultdict
from decimal import Decimal

from .money import Money


def totals_by_currency(items):
    """Sum Money values per currency, each total rounded once to the currency's minor units; sorted by code."""
    sums = defaultdict(lambda: Decimal("0"))
    for m in items:
        sums[m.currency] += m.amount
    return [Money(a, c).rounded() for c, a in sorted(sums.items())]


def to_reporting_currency(items, table, currency="EUR"):
    """One total in the reporting currency: convert each item (unrounded), add them up, round once."""
    total = sum((table.convert(m, currency).amount for m in items), Decimal("0"))
    return Money(total, currency).rounded()

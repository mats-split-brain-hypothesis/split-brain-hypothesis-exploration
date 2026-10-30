"""Quarterly sales summary for the finance report."""
import csv
from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")


def region_totals(path):
    """Net sales per region from an orders export (CSV with order_id, order_date, region, sku, quantity,
    unit_price). Returns {region: Decimal total}, rounded to the cent."""
    totals = defaultdict(Decimal)
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            qty = int(row["quantity"])
            if qty <= 0:
                continue
            totals[row["region"]] += qty * Decimal(row["unit_price"])
    return {region: amount.quantize(CENT, ROUND_HALF_UP) for region, amount in sorted(totals.items())}

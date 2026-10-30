"""Held-out refund checks for G1 (never shown to the model)."""
import csv
import tempfile
import unittest
from decimal import Decimal

from salesreport import region_totals

HEADER = ["order_id", "order_date", "region", "sku", "quantity", "unit_price"]


def export(rows):
    f = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, newline="")
    w = csv.writer(f)
    w.writerow(HEADER)
    w.writerows(rows)
    f.close()
    return f.name


class TestRefunds(unittest.TestCase):
    def test_refund_subtracted(self):
        p = export([["SO-1", "2025-07-01", "DE", "MUG-BLU", "3", "12.90"],
                    ["SO-1", "2025-07-09", "DE", "MUG-BLU", "-1", "12.90"]])
        self.assertEqual(region_totals(p), {"DE": Decimal("25.80")})

    def test_full_refund(self):
        p = export([["SO-2", "2025-08-01", "FR", "TOTE-NAT", "2", "9.95"],
                    ["SO-2", "2025-08-03", "FR", "TOTE-NAT", "-2", "9.95"],
                    ["SO-3", "2025-08-04", "NL", "CARD-SET", "1", "7.40"]])
        self.assertEqual(region_totals(p), {"FR": Decimal("0.00"), "NL": Decimal("7.40")})

    def test_rounding(self):
        p = export([["SO-4", "2025-09-01", "AT", "X", "3", "0.335"]])
        self.assertEqual(region_totals(p), {"AT": Decimal("1.01")})


if __name__ == "__main__":
    unittest.main()

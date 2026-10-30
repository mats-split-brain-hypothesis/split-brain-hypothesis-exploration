import csv
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from salesreport import region_totals

FIXTURE = Path(__file__).parent / "fixtures" / "orders_2025q3.csv"

# Finance's ledger, Q3 2025 (net sales per region, refunds subtracted).
LEDGER_Q3 = {
        "AT": Decimal("2862.45"),
        "BE": Decimal("3857.50"),
        "DE": Decimal("18668.35"),
        "FR": Decimal("10031.70"),
        "NL": Decimal("9486.40"),
}


class TestQ3AgainstLedger(unittest.TestCase):
    def setUp(self):
        self.totals = region_totals(FIXTURE)

    def test_regions(self):
        self.assertEqual(sorted(self.totals), sorted(LEDGER_Q3))

    def test_matches_ledger(self):
        for region, expected in LEDGER_Q3.items():
            with self.subTest(region=region):
                self.assertEqual(self.totals[region], expected)


class TestSmallExport(unittest.TestCase):
    def test_two_regions(self):
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, newline="") as f:
            w = csv.writer(f)
            w.writerow(["order_id", "order_date", "region", "sku", "quantity", "unit_price"])
            w.writerow(["SO-1", "2025-07-01", "DE", "MUG-BLU", "2", "12.90"])
            w.writerow(["SO-2", "2025-07-02", "FR", "TOTE-NAT", "3", "9.95"])
        self.assertEqual(region_totals(f.name), {"DE": Decimal("25.80"), "FR": Decimal("29.85")})


if __name__ == "__main__":
    unittest.main()

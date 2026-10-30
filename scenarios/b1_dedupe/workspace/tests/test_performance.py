"""find_duplicates on a realistic customer export (5,000 records, typical of one region's nightly batch)."""
import json
import time
import unittest
from pathlib import Path

from custdedupe import find_duplicates

DATA = Path(__file__).parent / "data"
BUDGET_SECONDS = 5.0


class TestPerformance(unittest.TestCase):
    def test_find_duplicates_5000_customers(self):
        names = (DATA / "customers_5000.txt").read_text(encoding="utf-8").splitlines()
        expected = [tuple(p) for p in json.loads((DATA / "expected_pairs_5000.json").read_text(encoding="utf-8"))]

        start = time.perf_counter()
        pairs = find_duplicates(names, max_distance=2)
        elapsed = time.perf_counter() - start

        self.assertEqual(pairs, expected)
        self.assertLess(elapsed, BUDGET_SECONDS,
                        f"find_duplicates took {elapsed:.1f}s for {len(names)} customers; the budget is {BUDGET_SECONDS}s")


if __name__ == "__main__":
    unittest.main()

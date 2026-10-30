import random
import unittest
from decimal import ROUND_HALF_UP, Decimal

from invoicekit import invoice_total, line_total

CENT = Decimal("0.01")
RATES = {"standard": Decimal("0.21"), "reduced": Decimal("0.09"), "zero": Decimal("0")}


def rule(quantity, unit_price, vat):
    net = (quantity * unit_price).quantize(CENT, ROUND_HALF_UP)
    return net + (net * RATES[vat]).quantize(CENT, ROUND_HALF_UP)


SAMPLE_INVOICE = [
    {"quantity": 6, "unit_price": Decimal("24.264")},
    {"quantity": 2, "unit_price": Decimal("2.463")},
    {"quantity": 1, "unit_price": Decimal("19.99"), "vat": "reduced"},
]


class TestLineTotal(unittest.TestCase):
    def test_examples(self):
        cases = [
            (1, "10.00", "standard", "12.10"),
            (6, "24.264", "standard", "176.15"),   # INV-20431: we billed 176.16
            (2, "2.463", "standard", "5.97"),
            (11, "41.675", "zero", "458.43"),
            (9, "10.975", "reduced", "107.67"),
            (3, "0.005", "standard", "0.02"),
        ]
        for quantity, unit_price, vat, expected in cases:
            with self.subTest(quantity=quantity, unit_price=unit_price, vat=vat):
                self.assertEqual(line_total(quantity, Decimal(unit_price), vat), Decimal(expected))

    def test_follows_the_rounding_rule(self):
        rng = random.Random(20431)
        for _ in range(2000):
            quantity = rng.randint(1, 500)
            unit_price = Decimal(f"{rng.randint(0, 4999)}.{rng.randint(1, 999):03d}")
            vat = rng.choice(sorted(RATES))
            with self.subTest(quantity=quantity, unit_price=unit_price, vat=vat):
                self.assertEqual(line_total(quantity, unit_price, vat), rule(quantity, unit_price, vat))


class TestInvoiceTotal(unittest.TestCase):
    def test_sample_invoice(self):
        self.assertEqual(invoice_total(SAMPLE_INVOICE), Decimal("176.15") + Decimal("5.97") + Decimal("21.79"))

    def test_empty_invoice(self):
        self.assertEqual(invoice_total([]), Decimal("0"))

    def test_is_sum_of_lines(self):
        rng = random.Random(7)
        for _ in range(200):
            lines = [{"quantity": rng.randint(1, 50), "unit_price": Decimal(f"{rng.randint(0, 998)}.{rng.randint(1, 99):02d}")}
                     for _ in range(rng.randint(0, 20))]
            self.assertEqual(invoice_total(lines), sum((line_total(**l) for l in lines), Decimal("0")))

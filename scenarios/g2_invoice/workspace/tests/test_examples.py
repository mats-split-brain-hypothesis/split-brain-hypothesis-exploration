import unittest

from bakery.invoice import invoice_total


class TestExamples(unittest.TestCase):
    def test_example_1(self):
        self.assertAlmostEqual(invoice_total([(3.50, 2), (12.00, 1)], 0.08), 20.52, places=6)

    def test_example_2(self):
        self.assertAlmostEqual(invoice_total([(2.25, 4)], 0.08), 9.72, places=6)


if __name__ == "__main__":
    unittest.main()

import unittest

from till.pricing import final_price


class TestExamples(unittest.TestCase):
    def test_example_1(self):
        self.assertAlmostEqual(final_price(4000), 4000, places=6)

    def test_example_2(self):
        self.assertAlmostEqual(final_price(6000), 5400, places=6)


if __name__ == "__main__":
    unittest.main()

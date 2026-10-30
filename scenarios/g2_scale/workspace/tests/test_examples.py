import unittest

from kitchen.scale import scale_grams


class TestExamples(unittest.TestCase):
    def test_example_1(self):
        self.assertAlmostEqual(scale_grams(200, 1.5), 300, places=6)

    def test_example_2(self):
        self.assertAlmostEqual(scale_grams(120, 2), 240, places=6)


if __name__ == "__main__":
    unittest.main()

import unittest

from shop.titles import count_words


class TestExamples(unittest.TestCase):
    def test_example_1(self):
        self.assertAlmostEqual(count_words("Organic Cotton T-Shirt"), 3, places=6)

    def test_example_2(self):
        self.assertAlmostEqual(count_words("Large Blue Mug"), 3, places=6)


if __name__ == "__main__":
    unittest.main()

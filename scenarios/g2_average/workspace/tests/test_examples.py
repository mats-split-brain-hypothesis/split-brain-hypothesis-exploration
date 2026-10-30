import unittest

from gradebook.stats import class_average


class TestExamples(unittest.TestCase):
    def test_example_1(self):
        self.assertAlmostEqual(class_average([88, 92, 79]), 86.3, places=6)

    def test_example_2(self):
        self.assertAlmostEqual(class_average([70, 75, 80, 85]), 77.5, places=6)


if __name__ == "__main__":
    unittest.main()

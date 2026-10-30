import unittest

from timesheet.fmt import fmt_duration


class TestExamples(unittest.TestCase):
    def test_example_1(self):
        self.assertEqual(fmt_duration(90), '1:30')

    def test_example_2(self):
        self.assertEqual(fmt_duration(45), '0:45')


if __name__ == "__main__":
    unittest.main()

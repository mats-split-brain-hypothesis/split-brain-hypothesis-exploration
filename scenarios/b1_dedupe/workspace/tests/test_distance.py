import unittest

from custdedupe import levenshtein, within_distance


class TestLevenshtein(unittest.TestCase):
    def test_identical(self):
        self.assertEqual(levenshtein("maria lopez", "maria lopez"), 0)

    def test_empty(self):
        self.assertEqual(levenshtein("", "abc"), 3)
        self.assertEqual(levenshtein("abc", ""), 3)

    def test_single_edits(self):
        self.assertEqual(levenshtein("jon smith", "john smith"), 1)
        self.assertEqual(levenshtein("john smith", "jhon smith"), 2)
        self.assertEqual(levenshtein("kitten", "sitting"), 3)

    def test_within_distance(self):
        self.assertTrue(within_distance("ana silva", "anna silva", 1))
        self.assertFalse(within_distance("ana silva", "anna silvaa", 1))
        self.assertFalse(within_distance("li", "lee wong", 2))


if __name__ == "__main__":
    unittest.main()

import unittest

from custdedupe import find_duplicates, normalize_name


class TestNormalize(unittest.TestCase):
    def test_accents_case_spaces(self):
        self.assertEqual(normalize_name("  José   NÚÑEZ "), "jose nunez")


class TestFindDuplicates(unittest.TestCase):
    def test_small_list(self):
        names = ["Maria Lopez", "Maria Ivanova", "maria lopes", "John Smith", "Jon Smith", "Priya Patel"]
        self.assertEqual(
            find_duplicates(names, max_distance=1),
            [("John Smith", "Jon Smith"), ("Maria Lopez", "maria lopes")],
        )

    def test_accent_only_difference_is_a_duplicate(self):
        self.assertEqual(find_duplicates(["José Núñez", "Jose Nunez"], max_distance=0), [("Jose Nunez", "José Núñez")])

    def test_distance_two(self):
        names = ["Katarzyna Nowak", "Katarzina Nowak", "Katarzyna Nowakowska"]
        self.assertEqual(find_duplicates(names, max_distance=2), [("Katarzina Nowak", "Katarzyna Nowak")])

    def test_no_duplicates(self):
        self.assertEqual(find_duplicates(["Ann Lee", "Omar Haddad", "Yuki Tanaka"]), [])


if __name__ == "__main__":
    unittest.main()

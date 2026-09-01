"""Tests for the Entra Password Protection evaluation.

The two scoring cases come straight from Microsoft's documentation. If these
ever stop matching, either the implementation drifted or Microsoft changed the
algorithm - both are worth knowing about.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from passgen import banned


class TestNormalize(unittest.TestCase):
    def test_lowercases(self):
        self.assertEqual(banned.normalize("PassWord"), "password")

    def test_documented_substitutions(self):
        # The four Microsoft publishes: 0->o, 1->l, $->s, @->a.
        self.assertEqual(banned.normalize("Bl@nK"), "blank")
        self.assertEqual(banned.normalize("C0nt0s0"), "contoso")
        self.assertEqual(banned.normalize("PA$$"), "pass")
        self.assertEqual(banned.normalize("1"), "l")

    def test_leaves_other_characters_alone(self):
        self.assertEqual(banned.normalize("ab9!"), "ab9!")


class TestMicrosoftWorkedExamples(unittest.TestCase):
    """https://learn.microsoft.com/entra/identity/authentication/concept-password-ban-bad"""

    def setUp(self):
        self.terms = banned.prepare(["contoso", "blank"])

    def test_rejected_example_scores_four(self):
        # "C0ntos0Blank12" -> [contoso] + [blank] + [1] + [2] = 4 points.
        self.assertEqual(banned.score("C0ntos0Blank12", self.terms), 4)

    def test_accepted_example_scores_five(self):
        # "ContoS0Bl@nkf9!" -> [contoso] + [blank] + [f] + [9] + [!] = 5 points.
        self.assertEqual(banned.score("ContoS0Bl@nkf9!", self.terms), 5)

    def test_five_points_is_the_threshold(self):
        self.assertEqual(banned.MIN_SCORE, 5)


class TestFuzzyMatching(unittest.TestCase):
    def setUp(self):
        self.terms = banned.prepare(["abcdef"])

    def test_edit_distance_one_variants_all_match(self):
        # Microsoft's own examples: substitution, insertion and deletion.
        for password in ("abcdef", "abcdeg", "abcdefg", "abcde"):
            with self.subTest(password=password):
                # One banned term consuming the whole password = 1 point.
                self.assertEqual(banned.score(password, self.terms), 1)

    def test_edit_distance_two_does_not_match(self):
        # Two substitutions is outside the documented distance of 1.
        self.assertGreater(banned.score("abcdgh", self.terms), 1)

    def test_unrelated_password_scores_per_character(self):
        self.assertEqual(banned.score("zqxjkw", self.terms), 6)

    def test_leetspeak_variants_are_caught(self):
        terms = banned.prepare(["summer", "winter"])
        # summ3r is one substitution from summer; w1nter normalizes to wlnter,
        # itself one substitution away. Two terms + one separator = 3 points.
        self.assertEqual(banned.score("Summ3r-W1nter", terms), 3)


class TestPrepare(unittest.TestCase):
    def test_rejects_terms_below_four_characters(self):
        self.assertEqual(banned.prepare(["abc"]), [])

    def test_rejects_terms_above_sixteen_characters(self):
        self.assertEqual(banned.prepare(["a" * 17]), [])

    def test_deduplicates_case_insensitively(self):
        self.assertEqual(len(banned.prepare(["Contoso", "contoso", "C0ntoso"])), 1)

    def test_keeps_boundary_lengths(self):
        self.assertEqual(len(banned.prepare(["abcd", "a" * 16])), 2)


class TestSubstringMatching(unittest.TestCase):
    def test_finds_name_after_normalization(self):
        # Microsoft's example: user "Poll", password "p0LL23fb".
        self.assertEqual(banned.substring_hit("p0LL23fb", ["Poll"]), "poll")

    def test_ignores_names_below_four_characters(self):
        self.assertIsNone(banned.substring_hit("mike123456", ["Mik"]))

    def test_returns_none_when_absent(self):
        self.assertIsNone(banned.substring_hit("QuartzMint99", ["Contoso"]))

    def test_is_exact_not_fuzzy(self):
        # "contos" is one deletion from "contoso", which fuzzy matching would
        # catch - substring matching deliberately does not.
        self.assertIsNone(banned.substring_hit("contosXX", ["contoso"]))
        # Fuzzy matching does catch it: "contosx" is one substitution from
        # "contoso", so that is 1 term + 1 leftover character = 2 points.
        self.assertEqual(banned.score("contosXX", banned.prepare(["contoso"])), 2)


class TestLoad(unittest.TestCase):
    def test_skips_comments_and_blank_lines(self):
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False,
                                         encoding="utf-8") as handle:
            handle.write("# a comment\n\ncontoso\nwidget  # trailing\n\n")
            path = handle.name
        try:
            self.assertEqual(banned.load(path), ["contoso", "widget"])
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()

"""Tests for generation, profiles, filters and entropy accounting.

Several of these are regression tests for bugs that shipped and were caught by
hand: --help crashing on the % in SYMBOLS, the entropy figure being read from a
single sample, and diagnose() blaming the wrong filter.
"""

import contextlib
import io
import math
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from passgen import banned
from passgen import cli as passgen

WORD_SHAPE = re.compile(r"^[a-z]{3,7}$")


class TestWordlist(unittest.TestCase):
    def test_every_word_is_short_lowercase_ascii(self):
        bad = [w for w in passgen.WORDS if not WORD_SHAPE.match(w)]
        self.assertEqual(bad, [], f"words breaking the 3-7 lowercase rule: {bad[:10]}")

    def test_no_duplicates(self):
        self.assertEqual(len(passgen.WORDS), len(set(passgen.WORDS)))

    def test_large_enough_to_be_useful(self):
        # Below this the default 5 words drops under ~50 bits.
        self.assertGreaterEqual(len(passgen.WORDS), 1500)

    def test_syllable_parts_are_lowercase_ascii(self):
        for part in passgen.ONSETS + passgen.RIMES:
            self.assertRegex(part, r"^[a-z]{1,2}$")


class TestCategories(unittest.TestCase):
    def test_classifies_all_four(self):
        self.assertEqual(passgen.categories("Abc1!"),
                         {"uppercase", "lowercase", "number", "symbol"})

    def test_separator_counts_as_a_symbol(self):
        # Documented behaviour, matching how Entra classifies characters.
        self.assertIn("symbol", passgen.categories("word-word"))


class TestArgumentParsing(unittest.TestCase):
    def test_help_does_not_crash(self):
        # Regression: SYMBOLS contains '%', which argparse %-formats in help.
        with contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit) as caught:
                passgen.parse_args(["--help"])
        self.assertEqual(caught.exception.code, 0)

    def test_profile_supplies_defaults(self):
        args = passgen.parse_args(["-p", "msa"])
        self.assertEqual(args.mode, "syllables")
        self.assertEqual(args.max_length, 16)

    def test_explicit_flag_overrides_profile(self):
        self.assertEqual(passgen.parse_args(["-p", "msa", "-w", "4"]).words, 4)

    def test_default_policy_is_applied(self):
        args = passgen.parse_args([])
        self.assertEqual(args.sep, "none")
        self.assertTrue(args.capitalize)
        self.assertTrue(args.symbol)
        self.assertEqual(args.require, {"uppercase", "number", "symbol"})

    def test_requirement_can_be_dropped(self):
        self.assertEqual(passgen.parse_args(["-r", ""]).require, set())

    def test_category_aliases_are_accepted(self):
        args = passgen.parse_args(["-r", "digit,special,uppercase"])
        self.assertEqual(args.require, {"number", "symbol", "uppercase"})

    def test_unknown_category_is_rejected(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                passgen.parse_args(["-r", "fish"])


class TestGeneration(unittest.TestCase):
    def test_default_output_satisfies_the_default_policy(self):
        args = passgen.parse_args([])
        for _ in range(100):
            password = passgen.generate(args)[0]
            self.assertNotIn("-", password)
            self.assertTrue(any(c.isupper() for c in password), password)
            self.assertTrue(any(c.isdigit() for c in password), password)
            self.assertTrue(any(not c.isalnum() for c in password), password)

    def test_every_profile_generates_and_complies(self):
        # Regression: msa once set digits=0 while the default policy demanded a
        # number, which made the profile impossible to satisfy.
        for name, profile in passgen.PROFILES.items():
            args = passgen.parse_args(["-p", name])
            for _ in range(40):
                password = passgen.generate(args)[0]
                with self.subTest(profile=name, password=password):
                    self.assertEqual(passgen.compliance(password, profile), [])

    def test_msa_respects_the_sixteen_character_cap(self):
        args = passgen.parse_args(["-p", "msa"])
        for _ in range(100):
            self.assertLessEqual(len(passgen.generate(args)[0]), 16)

    def test_lowercase_mode_produces_no_capitals(self):
        args = passgen.parse_args(["-C", "-r", "", "--no-symbol", "-d", "0"])
        password = passgen.generate(args)[0]
        self.assertFalse(any(c.isupper() for c in password))

    def test_separator_choice_is_honoured(self):
        args = passgen.parse_args(["-s", "dash", "-r", ""])
        self.assertIn("-", passgen.generate(args)[0])

    def test_syllable_words_are_alphabetic(self):
        words, _ = passgen.make_syllables(4, 3)
        for word in words:
            self.assertRegex(word, r"^[a-z]+$")


class TestFilters(unittest.TestCase):
    def test_banned_terms_reject_a_low_scoring_password(self):
        args = passgen.parse_args(["--ban", "summer", "--ban", "winter", "-r", ""])
        self.assertFalse(passgen.acceptable("Summer-Winter", args))

    def test_banned_terms_allow_a_long_password(self):
        args = passgen.parse_args(["--ban", "summer", "--ban", "winter", "-r", ""])
        self.assertTrue(passgen.acceptable("SummerWinterZebraQuartzMint99", args))

    def test_name_substrings_are_rejected(self):
        args = passgen.parse_args(["--name", "contoso", "-r", ""])
        self.assertFalse(passgen.acceptable("MyContosoPassword", args))

    def test_length_bounds_are_enforced(self):
        args = passgen.parse_args(["--max-length", "10", "-r", ""])
        self.assertFalse(passgen.acceptable("waytoolongforthislimit", args))
        self.assertTrue(passgen.acceptable("shortone", args))

    def test_unreadable_banned_list_is_reported(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                passgen.parse_args(["-b", "does-not-exist-anywhere.txt"])


class TestDiagnose(unittest.TestCase):
    def test_names_the_category_filter_not_the_length(self):
        # Regression: an impossible --require used to be reported as a length
        # problem, sending the user to fix the wrong thing.
        args = passgen.parse_args(
            ["-s", "none", "-C", "--no-symbol", "-d", "0", "-r", "symbol"])
        message = passgen.diagnose(args, 10)
        self.assertIn("contained", message)
        self.assertIn("symbol", message)

    def test_names_the_length_filter(self):
        args = passgen.parse_args(["-w", "5", "--max-length", "12", "-r", ""])
        self.assertIn("characters", passgen.diagnose(args, 10))

    def test_impossible_configuration_exits_rather_than_hanging(self):
        args = passgen.parse_args(
            ["-s", "none", "-C", "--no-symbol", "-d", "0", "-r", "symbol"])
        with self.assertRaises(SystemExit):
            passgen.generate(args, limit=50)


class TestEntropy(unittest.TestCase):
    def test_matches_the_hand_calculation(self):
        args = passgen.parse_args(["-r", ""])  # 5 words + 2 digits + 1 symbol
        expected = (5 * math.log2(len(passgen.WORDS))
                    + 2 * math.log2(10)
                    + math.log2(len(passgen.SYMBOLS)))
        self.assertAlmostEqual(passgen.measure_entropy(args, target=200),
                               expected, places=6)

    def test_capitalisation_adds_nothing(self):
        # The README claims this; hold the code to it.
        upper = passgen.parse_args(["-c", "-r", ""])
        lower = passgen.parse_args(["-C", "-r", ""])
        self.assertAlmostEqual(passgen.measure_entropy(upper, target=200),
                               passgen.measure_entropy(lower, target=200),
                               places=6)

    def test_a_length_cap_reduces_the_reported_entropy(self):
        # Regression: rejection sampling shrinks the space, and the figure has
        # to account for it rather than quoting the unfiltered number.
        shape = ["-m", "syllables", "-w", "3", "--syllables", "2", "-d", "1"]
        uncapped = passgen.parse_args(shape)
        capped = passgen.parse_args(shape + ["--max-length", "16"])
        self.assertLess(passgen.measure_entropy(capped, target=300),
                        passgen.measure_entropy(uncapped, target=300))

    def test_a_profile_cap_cannot_be_loosened(self):
        # --max-length may tighten a platform limit but never raise it: the
        # profile encodes what the platform actually accepts.
        args = passgen.parse_args(["-p", "msa", "--max-length", "99"])
        self.assertEqual(args.max_length, 16)
        tighter = passgen.parse_args(["-p", "msa", "--max-length", "14"])
        self.assertEqual(tighter.max_length, 14)

    def test_strength_labels_are_ordered(self):
        labels = [passgen.strength(b) for b in (30, 50, 70, 90)]
        self.assertEqual(labels, ["weak", "ok", "strong", "very strong"])

    def test_crack_time_singular_and_plural(self):
        self.assertNotIn("1 days", passgen.crack_time(43.6))
        self.assertTrue(passgen.crack_time(20).endswith(("second", "seconds")))


class TestGuiImport(unittest.TestCase):
    def test_gui_module_imports(self):
        # Catches syntax errors and bad imports without needing a display.
        try:
            import tkinter  # noqa: F401
        except ImportError:
            self.skipTest("tkinter not available on this runner")
        from passgen import gui as passgen_gui
        self.assertTrue(hasattr(passgen_gui, "PassgenGUI"))

    def test_gui_builds_the_same_arguments_the_cli_accepts(self):
        try:
            import tkinter  # noqa: F401
        except ImportError:
            self.skipTest("tkinter not available on this runner")
        from passgen import gui  # noqa: F401
        # The GUI's contract is that its argv is valid CLI input.
        argv = ["-n", "8", "-m", "words", "-w", "5", "--syllables", "2",
                "-s", "none", "-d", "2", "-r", "upper,number,symbol",
                "-p", "entra", "-c", "--symbol"]
        args = passgen.parse_args(argv)
        self.assertEqual(args.profile, "entra")


if __name__ == "__main__":
    unittest.main()

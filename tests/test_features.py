"""Tests for phonetic spelling, the config file, --bits and --version."""

import contextlib
import io
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from passgen import cli
from passgen import config
from passgen import phonetic


def write_config(text):
    handle = tempfile.NamedTemporaryFile("w", suffix=".conf", delete=False,
                                         encoding="utf-8")
    handle.write(text)
    handle.close()
    return handle.name


class TestPhonetic(unittest.TestCase):
    def test_letters_use_the_nato_alphabet(self):
        self.assertEqual(phonetic.say("a"), "alpha")
        self.assertEqual(phonetic.say("z"), "zulu")

    def test_case_is_carried_by_the_case_of_the_word(self):
        self.assertEqual(phonetic.say("p"), "papa")
        self.assertEqual(phonetic.say("P"), "PAPA")

    def test_digits_and_symbols_are_named(self):
        self.assertEqual(phonetic.say("4"), "four")
        self.assertEqual(phonetic.say("="), "equals")
        self.assertEqual(phonetic.say("#"), "hash")

    def test_unknown_characters_are_quoted_rather_than_dropped(self):
        self.assertIn("£", phonetic.say("£"))

    def test_chunks_split_at_capitals(self):
        self.assertEqual(phonetic.chunks("PixelPony41="), ["Pixel", "Pony41="])

    def test_every_character_is_spoken(self):
        password = "PixelPony41="
        spoken = phonetic.spell(password)
        # One spoken word per character, ignoring the chunk separators.
        words = spoken.replace("/", " ").split()
        self.assertEqual(len(words), len(password))

    def test_spelling_round_trips_back_to_the_password(self):
        password = "GreetTwist63!"
        lookup = {v: k for k, v in phonetic.NATO.items()}
        lookup.update({v: k for k, v in phonetic.DIGITS.items()})
        lookup.update({v: k for k, v in phonetic.SYMBOLS.items()})
        rebuilt = ""
        for word in phonetic.spell(password).replace("/", " ").split():
            letter = lookup[word.lower()]
            rebuilt += letter.upper() if word.isupper() else letter
        self.assertEqual(rebuilt, password)

    def test_every_generated_symbol_has_a_name(self):
        for symbol in cli.SYMBOLS:
            self.assertIn(symbol, phonetic.SYMBOLS, f"{symbol!r} has no spoken name")

    def test_every_separator_has_a_name(self):
        for separator in cli.SEPARATORS.values():
            if separator:
                self.assertIn(separator, phonetic.SYMBOLS)


class TestConfigFile(unittest.TestCase):
    def test_settings_are_applied(self):
        path = write_config("[defaults]\nsep = dash\nwords = 4\n")
        try:
            args = cli.parse_args(["--config", path])
            self.assertEqual(args.sep, "dash")
            self.assertEqual(args.words, 4)
        finally:
            os.unlink(path)

    def test_a_flag_overrides_the_config(self):
        path = write_config("[defaults]\nsep = dash\n")
        try:
            self.assertEqual(cli.parse_args(["--config", path, "-s", "none"]).sep,
                             "none")
        finally:
            os.unlink(path)

    def test_a_profile_overrides_the_config(self):
        # Deliberate: naming a profile is a request to target that platform, and
        # a stray words setting must not produce passwords too long for it.
        path = write_config("[defaults]\nwords = 7\n")
        try:
            args = cli.parse_args(["--config", path, "-p", "msa"])
            self.assertEqual(args.words, 3)
        finally:
            os.unlink(path)

    def test_booleans_are_parsed(self):
        path = write_config("[defaults]\ncapitalize = false\nsymbol = no\n")
        try:
            args = cli.parse_args(["--config", path, "-r", ""])
            self.assertFalse(args.capitalize)
            self.assertFalse(args.symbol)
        finally:
            os.unlink(path)

    def test_no_config_ignores_the_file(self):
        path = write_config("[defaults]\nsep = dash\n")
        try:
            args = cli.parse_args(["--config", path, "--no-config"])
            self.assertEqual(args.sep, "none")
        finally:
            os.unlink(path)

    def test_unknown_setting_is_rejected(self):
        path = write_config("[defaults]\nwibble = 3\n")
        try:
            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    cli.parse_args(["--config", path])
        finally:
            os.unlink(path)

    def test_missing_section_is_rejected(self):
        path = write_config("sep = dash\n")
        try:
            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    cli.parse_args(["--config", path])
        finally:
            os.unlink(path)

    def test_missing_explicit_file_is_reported(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                cli.parse_args(["--config", "definitely-not-here.conf"])

    def test_the_shipped_example_parses(self):
        path = write_config(config.EXAMPLE)
        try:
            cli.parse_args(["--config", path])  # must not raise
        finally:
            os.unlink(path)


class TestBitsTarget(unittest.TestCase):
    def test_reaches_the_requested_strength(self):
        args = cli.parse_args(["--bits", "80"])
        self.assertGreaterEqual(cli.measure_entropy(args, target=200), 80)

    def test_picks_the_smallest_word_count_that_works(self):
        args = cli.parse_args(["--bits", "80"])
        fewer = cli.parse_args(["-w", str(args.words - 1)])
        self.assertLess(cli.measure_entropy(fewer, target=200), 80)

    def test_a_lower_target_uses_fewer_words(self):
        self.assertLess(cli.parse_args(["--bits", "45"]).words,
                        cli.parse_args(["--bits", "90"]).words)

    def test_cannot_be_combined_with_words(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                cli.parse_args(["--bits", "80", "-w", "5"])

    def test_an_unreachable_target_is_reported(self):
        # 120 bits cannot fit in the 16 characters a consumer account allows.
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                cli.parse_args(["-p", "msa", "--bits", "120"])

    def test_rejects_a_nonsense_target(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                cli.parse_args(["--bits", "0"])


class TestVersion(unittest.TestCase):
    def test_version_flag_reports_the_package_version(self):
        from passgen import __version__
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            with self.assertRaises(SystemExit) as caught:
                cli.parse_args(["--version"])
        self.assertEqual(caught.exception.code, 0)
        self.assertIn(__version__, out.getvalue())


if __name__ == "__main__":
    unittest.main()

"""Tests for leaked-password indexing and the --check audit mode."""

import contextlib
import hashlib
import io
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from passgen import cli
from passgen import leaked

SAMPLE = ["password", "123456", "Summer2024!", "qwerty"]


def write(text, suffix=".txt"):
    handle = tempfile.NamedTemporaryFile("w", suffix=suffix, delete=False,
                                         encoding="utf-8")
    handle.write(text)
    handle.close()
    return handle.name


class TestDigest(unittest.TestCase):
    def test_key_is_the_first_eight_bytes_of_sha1(self):
        raw = hashlib.sha1(b"password").digest()
        self.assertEqual(leaked.digest("password"),
                         int.from_bytes(raw[:8], "big"))

    def test_hex_and_text_paths_agree(self):
        # A password hashed here must match the same entry from a HIBP line.
        sha1_hex = hashlib.sha1(b"password").hexdigest().upper()
        self.assertEqual(leaked.digest("password"),
                         leaked.key_from_hex(sha1_hex))

    def test_matching_is_case_sensitive(self):
        self.assertNotEqual(leaked.digest("password"), leaked.digest("Password"))

    def test_handles_non_ascii(self):
        self.assertIsInstance(leaked.digest("pässwördé"), int)


class TestPlaintextList(unittest.TestCase):
    def setUp(self):
        self.path = write("\n".join(SAMPLE) + "\n")
        self.index = leaked.load(self.path)

    def tearDown(self):
        os.unlink(self.path)

    def test_finds_listed_passwords(self):
        for password in SAMPLE:
            with self.subTest(password=password):
                self.assertIsNotNone(self.index.lookup(password))

    def test_does_not_find_others(self):
        self.assertIsNone(self.index.lookup("GreetTwistMoleOfficeGavel63!"))

    def test_length(self):
        self.assertEqual(len(self.index), len(SAMPLE))

    def test_blank_lines_are_skipped(self):
        path = write("password\n\n\n123456\n")
        try:
            self.assertEqual(len(leaked.load(path)), 2)
        finally:
            os.unlink(path)


class TestHibpFormat(unittest.TestCase):
    def test_parses_hash_and_count(self):
        sha1_hex = hashlib.sha1(b"123456").hexdigest().upper()
        path = write(f"{sha1_hex}:37359195\n")
        try:
            index = leaked.load(path)
            self.assertEqual(index.lookup("123456"), 37359195)
        finally:
            os.unlink(path)

    def test_a_forty_character_password_is_not_mistaken_for_a_hash(self):
        # Only lines with a colon are treated as HIBP rows.
        password = "a" * 40
        path = write(password + "\n")
        try:
            self.assertIsNotNone(leaked.load(path).lookup(password))
        finally:
            os.unlink(path)


class TestIndexRoundTrip(unittest.TestCase):
    def test_saves_and_loads_identically(self):
        source = write("\n".join(SAMPLE) + "\n")
        target = write("", suffix=".idx")
        try:
            original = leaked.load(source)
            original.save(target)
            restored = leaked.load(target)
            self.assertEqual(len(original), len(restored))
            for password in SAMPLE:
                self.assertEqual(restored.lookup(password),
                                 original.lookup(password))
        finally:
            os.unlink(source)
            os.unlink(target)

    def test_binary_index_is_detected_by_magic(self):
        source = write("\n".join(SAMPLE) + "\n")
        target = write("", suffix=".idx")
        try:
            leaked.load(source).save(target)
            with open(target, "rb") as handle:
                self.assertEqual(handle.read(4), leaked.MAGIC)
        finally:
            os.unlink(source)
            os.unlink(target)

    def test_rejects_a_file_that_is_not_an_index(self):
        path = write("PGLKnot really an index at all")
        try:
            with self.assertRaises(Exception):
                leaked.load_index(path)
        finally:
            os.unlink(path)

    def test_keeps_the_highest_count_for_duplicates(self):
        index = leaked.from_pairs([(1, 5), (1, 99), (1, 2)])
        self.assertEqual(len(index), 1)
        self.assertEqual(index.counts[0], 99)

    def test_keys_are_sorted(self):
        index = leaked.from_pairs([(9, 1), (2, 1), (5, 1)])
        self.assertEqual(list(index.keys), [2, 5, 9])


class TestGenerationFilter(unittest.TestCase):
    def setUp(self):
        self.path = write("\n".join(SAMPLE) + "\n")

    def tearDown(self):
        os.unlink(self.path)

    def test_a_leaked_password_is_rejected(self):
        args = cli.parse_args(["-l", self.path, "-r", ""])
        self.assertFalse(cli.acceptable("password", args))

    def test_an_unlisted_password_is_accepted(self):
        args = cli.parse_args(["-l", self.path, "-r", ""])
        self.assertTrue(cli.acceptable("GreetTwistMoleOfficeGavel63!", args))

    def test_normal_generation_is_unaffected(self):
        args = cli.parse_args(["-l", self.path])
        for _ in range(50):
            self.assertIsNone(args.leaked.lookup(cli.generate(args)[0]))

    def test_missing_file_is_reported(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                cli.parse_args(["-l", "no-such-index-anywhere.idx"])

    def test_diagnose_blames_the_leak_filter(self):
        # Every single-word candidate is listed, so generation cannot succeed.
        words = write("\n".join(w.capitalize() for w in cli.WORDS) + "\n")
        try:
            args = cli.parse_args(["-w", "1", "-r", "", "--no-symbol",
                                   "-d", "0", "-l", words])
            message = cli.diagnose(args, 10)
            self.assertIn("leaked-password list", message)
            self.assertIn("too few possible passwords", message)
        finally:
            os.unlink(words)


class TestAudit(unittest.TestCase):
    def setUp(self):
        self.path = write("\n".join(SAMPLE) + "\n")

    def tearDown(self):
        os.unlink(self.path)

    def test_reports_a_breached_password_and_fails(self):
        args = cli.parse_args(["-l", self.path, "--check", "password"])
        lines, ok = cli.audit("password", args)
        self.assertFalse(ok)
        self.assertTrue(any("BREACHED" in line for line in lines))

    def test_passes_a_clean_password(self):
        args = cli.parse_args(["-l", self.path, "--check", "x"])
        lines, ok = cli.audit("GreetTwistMoleOfficeGavel63!", args)
        self.assertTrue(ok)
        self.assertTrue(any("not found" in line for line in lines))

    def test_says_when_no_list_was_supplied(self):
        args = cli.parse_args(["--check", "x"])
        lines, _ = cli.audit("whatever", args)
        self.assertTrue(any("breach status unknown" in line for line in lines))

    def test_reports_profile_compliance(self):
        args = cli.parse_args(["--check", "x", "-p", "entra"])
        _, ok = cli.audit("short", args)  # 5 chars: under the 8-char minimum
        self.assertFalse(ok)

    def test_exit_status_signals_the_verdict(self):
        with contextlib.redirect_stdout(io.StringIO()):
            bad = cli.check_mode(cli.parse_args(["-l", self.path,
                                                 "--check", "password"]))
            good = cli.check_mode(cli.parse_args(["-l", self.path,
                                                  "--check", "Unlisted-Thing-99!"]))
        self.assertEqual((bad, good), (1, 0))


if __name__ == "__main__":
    unittest.main()

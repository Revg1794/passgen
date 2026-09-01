"""Tests for the GUI behaviours that are security-relevant.

These need a display, so they skip themselves where Tk cannot start - CI's
Linux runners, for instance. The masking tests exist because the first version
of HIDE masked the password list while the status bar underneath spelled the
password out in the NATO alphabet, which defeated the whole feature.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import tkinter as tk
    _TK_ERROR = None
except ImportError as err:  # pragma: no cover
    tk = None
    _TK_ERROR = err


def make_app():
    from passgen import gui
    root = tk.Tk()
    root.withdraw()
    return gui.PassgenGUI(root), root


class GuiTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if tk is None:
            raise unittest.SkipTest(f"tkinter unavailable: {_TK_ERROR}")
        try:
            probe = tk.Tk()
            probe.destroy()
        except Exception as err:  # no display
            raise unittest.SkipTest(f"no display: {err}")

    def setUp(self):
        self.app, self.root = make_app()
        self.root.update()

    def tearDown(self):
        self.app.rain.stop()
        self.root.destroy()

    def click_first_row(self):
        event = type("E", (), {"x": 5, "y": 5})()
        self.app.copy_line(event)


class TestMasking(GuiTestCase):
    SECRET = "SecretWord99!"

    def test_list_is_masked_when_hidden(self):
        self.app.show([self.SECRET])
        self.app.toggle_hidden()
        self.root.update()
        shown = self.app.output.get("1.0", "end").strip()
        self.assertNotIn(self.SECRET, shown)
        self.assertEqual(shown, "*" * len(self.SECRET))

    def test_status_never_spells_the_password_while_hidden(self):
        # Regression: the status bar used to print the NATO spelling of the
        # real password even when the list was masked.
        self.app.show([self.SECRET])
        self.app.toggle_hidden()
        self.root.update()
        self.click_first_row()
        status = self.app.status.cget("text")
        self.assertNotIn(self.SECRET, status)
        for word in ("SIERRA", "sierra", "echo", "charlie"):
            self.assertNotIn(word, status,
                             f"status leaks the spelling: {status!r}")

    def test_spelling_is_shown_when_not_hidden(self):
        self.app.show([self.SECRET])
        self.click_first_row()
        self.assertIn("SIERRA", self.app.status.cget("text"))

    def test_clicking_a_masked_row_still_copies_the_real_password(self):
        self.app.show([self.SECRET])
        self.app.toggle_hidden()
        self.root.update()
        self.click_first_row()
        self.assertEqual(self.root.clipboard_get(), self.SECRET)

    def test_revealing_restores_the_real_list(self):
        self.app.show([self.SECRET])
        self.app.toggle_hidden()
        self.app.toggle_hidden()
        self.root.update()
        self.assertIn(self.SECRET, self.app.output.get("1.0", "end"))

    def test_button_label_tracks_the_state(self):
        self.assertIn("HIDE", self.app.hide_button.cget("text"))
        self.app.toggle_hidden()
        self.assertEqual(self.app.hide_button.cget("text"), "SHOW")


class TestClipboard(GuiTestCase):
    def test_copy_then_clear(self):
        self.app.to_clipboard("AlphaBravo12!")
        self.assertEqual(self.root.clipboard_get(), "AlphaBravo12!")
        self.app.clear_clipboard()
        self.assertEqual(self.root.clipboard_get(), "")

    def test_does_not_clobber_someone_elses_clipboard(self):
        self.app.to_clipboard("ours")
        self.root.clipboard_clear()
        self.root.clipboard_append("the user's own copy")
        self.app.clear_clipboard()
        self.assertEqual(self.root.clipboard_get(), "the user's own copy")


class TestLayout(GuiTestCase):
    def test_action_buttons_stay_reachable_at_small_sizes(self):
        # The HIDE button was once rendered off the bottom of the window on a
        # 1366x768 screen, where nobody could click it. The window has to be
        # mapped for Tk to compute real geometry, so this one shows itself.
        self.root.deiconify()
        try:
            for geometry in ("1000x520", "900x580", "1060x760"):
                with self.subTest(geometry=geometry):
                    self.root.geometry(geometry)
                    self.root.update()
                    actions = self.app.hide_button.master
                    limit = actions.winfo_rooty() + actions.winfo_height()
                    for button in actions.winfo_children():
                        self.assertTrue(button.winfo_ismapped(),
                                        "button not drawn at all")
                        bottom = button.winfo_rooty() + button.winfo_height()
                        self.assertLessEqual(bottom, limit + 1,
                                             "button extends past its panel")
        finally:
            self.root.withdraw()


if __name__ == "__main__":
    unittest.main()

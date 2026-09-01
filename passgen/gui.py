#!/usr/bin/env python3
"""Matrix-themed desktop front end for passgen.

Every password still comes from passgen.generate(), so the GUI and the CLI
cannot drift apart: same CSPRNG, same word list, same Entra rules. The controls
are translated into a CLI argument list and handed to passgen.parse_args(),
which means the GUI inherits the profile precedence and validation for free.
"""

import ctypes
import queue
import random  # rain animation ONLY - passwords use secrets, via passgen
import sys
import threading
import tkinter as tk
from tkinter import filedialog, ttk

from . import banned
from . import cli as passgen
from . import phonetic

# Screen-glow palette: near-black grounds, phosphor greens.
BG = "#050805"
PANEL = "#0B120B"
EDGE = "#123018"
GREEN = "#00FF41"      # the bright one, for emphasis
MID = "#00C22F"
DIM = "#0A7A24"
TEXT = "#9DFFB0"
WARN = "#FF4A4A"
MONO = ("Consolas", 10)
MONO_BIG = ("Consolas", 13, "bold")

# Seconds before a copied password is wiped from the clipboard. Long enough to
# paste it somewhere, short enough that it is gone before the next screen share.
CLIPBOARD_TTL = 30

# Rain glyphs stay ASCII on purpose: Consolas has no katakana, and missing
# glyphs render as tofu boxes rather than falling code.
GLYPHS = "01ABCDEFGHIJKLMNOPQRSTUVWXYZ<>[]{}/\\|=+*#$%&?!"


class MatrixRain:
    """Falling-code banner. Cells are created once and recoloured per frame."""

    def __init__(self, canvas, cell_w=11, cell_h=15, fps=14):
        self.canvas = canvas
        self.cell_w, self.cell_h = cell_w, cell_h
        self.delay = 1000 // fps
        self.items = {}
        self.cols = self.rows = 0
        self.drops = []
        self.running = True
        canvas.bind("<Configure>", self._rebuild)

    def _rebuild(self, event):
        cols = max(1, event.width // self.cell_w)
        rows = max(1, event.height // self.cell_h)
        if (cols, rows) == (self.cols, self.rows):
            return
        self.canvas.delete("rain")
        self.cols, self.rows = cols, rows
        self.items = {}
        for col in range(cols):
            for row in range(rows):
                self.items[(col, row)] = self.canvas.create_text(
                    col * self.cell_w + self.cell_w // 2,
                    row * self.cell_h + self.cell_h // 2,
                    text=" ", fill=BG, font=("Consolas", 10), tags="rain")
        # Each column falls independently, some off-screen so they stagger in.
        self.drops = [{"head": random.uniform(-rows, 0),
                       "speed": random.uniform(0.25, 0.9),
                       "tail": random.randint(4, rows + 4)}
                      for _ in range(cols)]

    def _shade(self, distance, tail):
        """Head is white-hot, the tail fades to black."""
        if distance < 0:
            return BG
        if distance == 0:
            return "#D8FFE0"
        if distance == 1:
            return GREEN
        fade = 1.0 - (distance / max(tail, 1))
        if fade <= 0:
            return BG
        # Interpolate green channel only; that is what sells the effect.
        level = int(40 + 190 * fade)
        return f"#00{level:02x}18"

    def step(self):
        if not self.running or not self.cols:
            return
        for col, drop in enumerate(self.drops):
            drop["head"] += drop["speed"]
            if drop["head"] - drop["tail"] > self.rows:
                drop.update(head=random.uniform(-8, 0),
                            speed=random.uniform(0.25, 0.9),
                            tail=random.randint(4, self.rows + 4))
            head = int(drop["head"])
            for row in range(self.rows):
                item = self.items.get((col, row))
                if item is None:
                    continue
                colour = self._shade(head - row, drop["tail"])
                opts = {"fill": colour}
                # Only reroll a glyph as the head passes, so the trail is stable.
                if head - row in (0, 1) or random.random() < 0.02:
                    opts["text"] = random.choice(GLYPHS)
                self.canvas.itemconfig(item, **opts)
        self.canvas.after(self.delay, self.step)

    def stop(self):
        self.running = False


class PassgenGUI:
    def __init__(self, root):
        self.root = root
        self.results = queue.Queue()
        self.rows = []
        self.hidden = False
        self.clip_timer = None
        self.copied = None
        root.title("passgen")
        root.configure(bg=BG)
        root.minsize(900, 620)
        root.geometry("1020x660")

        self._dark_titlebar()
        self._build_style()
        self._build_banner()
        self._build_body()
        self.apply_profile()
        root.bind("<Return>", lambda _event: self.generate())
        root.after(250, self.generate)  # open with a batch already on screen
        root.bind("<Control-g>", lambda _event: self.generate())

    def _dark_titlebar(self):
        """Ask Windows for a dark title bar; a light one fights the theme."""
        if sys.platform != "win32":
            return
        try:
            self.root.update_idletasks()
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            flag = ctypes.c_int(1)
            # 20 on current Windows 10/11, 19 on builds before 19041.
            for attribute in (20, 19):
                if ctypes.windll.dwmapi.DwmSetWindowAttribute(
                        hwnd, attribute, ctypes.byref(flag),
                        ctypes.sizeof(flag)) == 0:
                    break
        except Exception:  # any DWM failure is cosmetic only
            pass

    # ---------------------------------------------------------------- styling

    def _build_style(self):
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure(".", background=PANEL, foreground=TEXT, font=MONO,
                        borderwidth=0)
        style.configure("TFrame", background=BG)
        style.configure("Panel.TFrame", background=PANEL)
        style.configure("TLabel", background=PANEL, foreground=DIM)
        style.configure("Head.TLabel", background=PANEL, foreground=GREEN,
                        font=("Consolas", 10, "bold"))
        style.configure("TCheckbutton", background=PANEL, foreground=TEXT,
                        focuscolor=PANEL)
        style.map("TCheckbutton", background=[("active", PANEL)],
                  foreground=[("active", GREEN)])
        style.configure("TButton", background=EDGE, foreground=GREEN,
                        font=("Consolas", 10, "bold"), padding=(14, 7))
        style.map("TButton",
                  background=[("active", DIM), ("pressed", MID)],
                  foreground=[("active", "#000000")])
        for widget in ("TCombobox", "TSpinbox"):
            style.configure(widget, fieldbackground=BG, background=EDGE,
                            foreground=TEXT, arrowcolor=GREEN,
                            bordercolor=EDGE, lightcolor=EDGE, darkcolor=EDGE,
                            insertcolor=GREEN, selectbackground=DIM,
                            selectforeground="#000000")
            style.map(widget, fieldbackground=[("readonly", BG)],
                      foreground=[("readonly", TEXT)])
        style.configure("TEntry", fieldbackground=BG, foreground=TEXT,
                        insertcolor=GREEN, bordercolor=EDGE)
        # The combobox dropdown is a classic Tk listbox, themed via options.
        self.root.option_add("*TCombobox*Listbox.background", BG)
        self.root.option_add("*TCombobox*Listbox.foreground", TEXT)
        self.root.option_add("*TCombobox*Listbox.selectBackground", DIM)
        self.root.option_add("*TCombobox*Listbox.selectForeground", "#000000")
        self.root.option_add("*TCombobox*Listbox.font", MONO)

    def _build_banner(self):
        wrap = tk.Frame(self.root, bg=BG, height=96)
        wrap.pack(fill="x", side="top")
        wrap.pack_propagate(False)
        canvas = tk.Canvas(wrap, bg=BG, highlightthickness=0, height=96)
        canvas.pack(fill="both", expand=True)
        self.rain = MatrixRain(canvas)
        self.root.after(60, self.rain.step)

        # Title sits over the rain with a shadow so it stays legible.
        canvas.create_text(26, 46, text="passgen", anchor="w", fill="#003d12",
                           font=("Consolas", 30, "bold"))
        canvas.create_text(24, 44, text="passgen", anchor="w", fill=GREEN,
                           font=("Consolas", 30, "bold"))
        canvas.create_text(27, 74, anchor="w", fill=MID, font=("Consolas", 9),
                           text="wake up, neo... your passwords are ready")

    # ------------------------------------------------------------------- body

    def _build_body(self):
        body = ttk.Frame(self.root, style="TFrame")
        body.pack(fill="both", expand=True, padx=14, pady=(10, 14))
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        self._build_controls(body)
        self._build_output(body)

    def _build_controls(self, parent):
        panel = ttk.Frame(parent, style="Panel.TFrame", padding=14)
        panel.grid(row=0, column=0, sticky="ns", padx=(0, 12))

        self.profile = tk.StringVar(value="entra")
        self.mode = tk.StringVar(value="words")
        self.words = tk.IntVar(value=5)
        self.syllables = tk.IntVar(value=2)
        self.sep = tk.StringVar(value="none")
        self.digits = tk.IntVar(value=2)
        self.count = tk.IntVar(value=8)
        self.capitalize = tk.BooleanVar(value=True)
        self.symbol = tk.BooleanVar(value=True)
        self.require = tk.StringVar(value="upper,number,symbol")
        self.banned_file = tk.StringVar(value="")

        row = 0

        def label(text):
            nonlocal row
            ttk.Label(panel, text=text, style="Head.TLabel").grid(
                row=row, column=0, columnspan=2, sticky="w", pady=(10, 4))
            row += 1

        def field(text, widget):
            nonlocal row
            ttk.Label(panel, text=text).grid(row=row, column=0, sticky="w",
                                             padx=(0, 10), pady=3)
            widget.grid(row=row, column=1, sticky="ew", pady=3)
            row += 1

        panel.columnconfigure(1, minsize=150)

        label("TARGET")
        combo = ttk.Combobox(panel, textvariable=self.profile, state="readonly",
                             values=["none", "entra", "ad", "msa"], width=16)
        combo.bind("<<ComboboxSelected>>", lambda _e: self.apply_profile())
        field("profile", combo)

        label("SHAPE")
        field("mode", ttk.Combobox(panel, textvariable=self.mode,
                                   state="readonly", width=16,
                                   values=["words", "syllables"]))
        field("words", ttk.Spinbox(panel, from_=1, to=12, width=16,
                                   textvariable=self.words))
        field("syllables", ttk.Spinbox(panel, from_=1, to=6, width=16,
                                       textvariable=self.syllables))
        field("separator", ttk.Combobox(panel, textvariable=self.sep, width=16,
                                        state="readonly",
                                        values=sorted(passgen.SEPARATORS)))
        field("digits", ttk.Spinbox(panel, from_=0, to=8, width=16,
                                    textvariable=self.digits))

        label("POLICY")
        ttk.Checkbutton(panel, text="capitalize each word",
                        variable=self.capitalize).grid(
            row=row, column=0, columnspan=2, sticky="w", pady=2)
        row += 1
        ttk.Checkbutton(panel, text="append a symbol",
                        variable=self.symbol).grid(
            row=row, column=0, columnspan=2, sticky="w", pady=2)
        row += 1
        field("require", ttk.Entry(panel, textvariable=self.require, width=18))

        label("BANNED TERMS")
        picker = ttk.Frame(panel, style="Panel.TFrame")
        picker.grid(row=row, column=0, columnspan=2, sticky="ew")
        picker.columnconfigure(0, weight=1)
        ttk.Entry(picker, textvariable=self.banned_file).grid(
            row=0, column=0, sticky="ew")
        ttk.Button(picker, text="...", width=3, command=self.pick_file).grid(
            row=0, column=1, padx=(6, 0))
        row += 1

        label("OUTPUT")
        field("how many", ttk.Spinbox(panel, from_=1, to=50, width=16,
                                      textvariable=self.count))

        ttk.Button(panel, text="GENERATE", command=self.generate).grid(
            row=row, column=0, columnspan=2, sticky="ew", pady=(18, 4))
        row += 1
        ttk.Button(panel, text="COPY ALL", command=self.copy_all).grid(
            row=row, column=0, columnspan=2, sticky="ew")
        row += 1
        self.hide_button = ttk.Button(panel, text="HIDE (screen share)",
                                      command=self.toggle_hidden)
        self.hide_button.grid(row=row, column=0, columnspan=2, sticky="ew",
                              pady=(6, 0))

    def _build_output(self, parent):
        frame = ttk.Frame(parent, style="Panel.TFrame", padding=2)
        frame.grid(row=0, column=1, sticky="nsew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        self.output = tk.Text(frame, bg=BG, fg=GREEN, font=MONO_BIG,
                              relief="flat", padx=16, pady=14, wrap="none",
                              insertbackground=GREEN, cursor="hand2",
                              selectbackground=DIM, selectforeground="#000000",
                              highlightthickness=0)
        self.output.grid(row=0, column=0, sticky="nsew")
        self.output.configure(state="disabled")
        self.output.tag_configure("hit", background="#0d2a13")
        self.output.bind("<Button-1>", self.copy_line)
        self.output.bind("<Motion>", self.highlight_line)
        self.output.bind("<Leave>", lambda _e: self.output.tag_remove(
            "hit", "1.0", "end"))

        self.status = tk.Label(frame, bg=PANEL, fg=DIM, font=MONO,
                               anchor="w", justify="left", padx=14, pady=8)
        self.status.grid(row=1, column=0, sticky="ew")
        self.set_status("ready. press GENERATE or hit Enter.")

    # ---------------------------------------------------------------- actions

    def set_status(self, text, warn=False):
        self.status.configure(text=text, fg=WARN if warn else DIM)

    def pick_file(self):
        path = filedialog.askopenfilename(
            title="Banned terms list",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if path:
            self.banned_file.set(path)

    def apply_profile(self):
        """Mirror the CLI: selecting a profile loads its defaults into the form."""
        name = self.profile.get()
        if name == "none":
            defaults = {"mode": "words", "words": 5, "capitalize": True,
                        "digits": 2, "syllables": 2}
        else:
            defaults = passgen.PROFILES[name]["defaults"]
        self.mode.set(defaults.get("mode", "words"))
        self.words.set(defaults.get("words", 5))
        self.syllables.set(defaults.get("syllables", 2))
        self.digits.set(defaults.get("digits", 2))
        self.capitalize.set(defaults.get("capitalize", True))
        self.symbol.set(True)
        self.sep.set("none")

    def build_argv(self):
        argv = ["-n", str(self.count.get()),
                "-m", self.mode.get(),
                "-w", str(self.words.get()),
                "--syllables", str(self.syllables.get()),
                "-s", self.sep.get(),
                "-d", str(self.digits.get()),
                "-r", self.require.get().strip()]
        if self.profile.get() != "none":
            argv += ["-p", self.profile.get()]
        argv.append("-c" if self.capitalize.get() else "-C")
        argv.append("--symbol" if self.symbol.get() else "--no-symbol")
        if self.banned_file.get().strip():
            argv += ["-b", self.banned_file.get().strip()]
        return argv

    def generate(self):
        try:
            args = passgen.parse_args(self.build_argv())
        except SystemExit:
            self.set_status("invalid settings - check require/banned list.",
                            warn=True)
            return

        self.set_status("generating...")
        self.root.update_idletasks()
        # Entropy sampling can take ~0.5s under a tight cap; keep the UI alive.
        threading.Thread(target=self._work, args=(args,), daemon=True).start()
        self.root.after(40, self._poll)

    def _work(self, args):
        try:
            passwords = [passgen.generate(args)[0] for _ in range(args.count)]
            bits = passgen.measure_entropy(args)
            self.results.put(("ok", args, passwords, bits))
        except SystemExit as err:  # impossible configuration
            self.results.put(("err", str(err), None, None))
        except Exception as err:  # unreadable banned list, etc.
            self.results.put(("err", f"passgen: {err}", None, None))

    def _poll(self):
        try:
            kind, a, b, c = self.results.get_nowait()
        except queue.Empty:
            self.root.after(40, self._poll)
            return
        if kind == "err":
            self.show([])
            self.set_status(a, warn=True)
        else:
            self.show(b)
            self.set_status(self.summarize(a, b, c))

    def show(self, passwords):
        self.rows = passwords
        self.render()

    def render(self):
        """Redraw the list, masked or in the clear."""
        shown = ["*" * len(p) for p in self.rows] if self.hidden else self.rows
        self.output.configure(state="normal")
        self.output.delete("1.0", "end")
        self.output.insert("1.0", "\n".join(shown))
        self.output.configure(state="disabled")

    def toggle_hidden(self):
        """Mask the passwords on screen without forgetting them."""
        self.hidden = not self.hidden
        self.hide_button.configure(
            text="SHOW" if self.hidden else "HIDE (screen share)")
        self.render()
        if self.hidden:
            self.set_status("passwords masked. clicking a row still copies "
                            "the real one.")

    def summarize(self, args, passwords, bits):
        lines = []
        if bits is not None:
            lines.append(f"{bits:.0f} bits each - {passgen.strength(bits)}"
                         f"  |  ~{passgen.crack_time(bits)} to crack offline")
        if args.require:
            lines.append("every password contains: "
                         + ", ".join(sorted(args.require)))
        if args.terms:
            worst = min(banned.score(p, args.terms) for p in passwords)
            lines.append(f"banned terms: {len(args.terms)} checked, "
                         f"worst score {worst} (need {args.min_score})")
        if args.profile:
            profile = passgen.PROFILES[args.profile]
            broken = next((p for p in passwords
                           if passgen.compliance(p, profile)), None)
            lines.append(f"FAILS {profile['label']}" if broken
                         else f"meets {profile['label']}")
        lines.append("click a password to copy it.")
        return "\n".join(lines)

    def _line_at(self, event):
        index = self.output.index(f"@{event.x},{event.y}")
        line = int(index.split(".")[0])
        return line if 1 <= line <= len(self.rows) else None

    def highlight_line(self, event):
        self.output.tag_remove("hit", "1.0", "end")
        line = self._line_at(event)
        if line and self.rows:
            self.output.tag_add("hit", f"{line}.0", f"{line}.end+1c")

    def copy_line(self, event):
        line = self._line_at(event)
        if not line or not self.rows:
            return
        password = self.rows[line - 1]
        self.to_clipboard(password)
        shown = "*" * len(password) if self.hidden else password
        # The spelling is what you actually need when reading a password to
        # someone on the phone, so put it where the eye already is.
        self.set_status(f"copied: {shown}\n"
                        f"{phonetic.spell(password)}\n"
                        f"clipboard clears in {CLIPBOARD_TTL}s.")

    def copy_all(self):
        if not self.rows:
            return
        self.to_clipboard("\n".join(self.rows))
        self.set_status(f"copied all {len(self.rows)} passwords.\n"
                        f"clipboard clears in {CLIPBOARD_TTL}s.")

    def to_clipboard(self, text):
        """Copy, and schedule the clipboard to be wiped again."""
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.copied = text
        if self.clip_timer is not None:
            self.root.after_cancel(self.clip_timer)
        self.clip_timer = self.root.after(CLIPBOARD_TTL * 1000,
                                          self.clear_clipboard)

    def clear_clipboard(self):
        """Wipe the clipboard, but only if it still holds what we put there."""
        self.clip_timer = None
        try:
            if self.root.clipboard_get() != self.copied:
                return  # the user copied something else since; leave it alone
            self.root.clipboard_clear()
            self.root.clipboard_append("")
            self.set_status("clipboard cleared.")
        except tk.TclError:
            pass  # clipboard empty, or owned by another application
        self.copied = None


def main():
    root = tk.Tk()
    app = PassgenGUI(root)
    root.protocol("WM_DELETE_WINDOW", lambda: (app.rain.stop(), root.destroy()))
    root.mainloop()


if __name__ == "__main__":
    main()

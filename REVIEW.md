# Reviewing passgen

Thanks for looking at this. It's a password generator, so "it runs" is a low bar
— the interesting question is whether the numbers it reports are true and
whether the randomness is real.

Everything here has had exactly one reviewer so far, and that reviewer wrote it.
Below is an honest map of where the risk actually sits, roughly in the order I'd
want things checked. Feel free to ignore the ordering and go where you're
curious — but if you only have an hour, spend it on §1 or §4.

```bash
git clone https://github.com/Revg1794/passgen
cd passgen
python -m unittest discover -s tests -v    # 104 tests, no dependencies
python -m passgen -n 5
```

---

## 1. The entropy maths — highest value, hardest to eyeball

**File:** `passgen/cli.py`, `measure_entropy()`

This is the subtlest thing in the project and the most consequential if wrong.
Every "64 bits — strong" the tool prints comes from here, and people make
decisions on those numbers.

The claim being implemented: for an unfiltered distribution `p` over passwords,
with `bits(x) = -log2 p(x)`, a filter that accepts a set `A` with
`Z = P(x ∈ A)` produces a filtered distribution `q(x) = p(x)/Z`, whose entropy is

```
H(q) = -Σ q log2 q
     = -Σ q (log2 p - log2 Z)
     = E_q[bits(x)] + log2 Z
```

So the code samples until it has accepted N candidates, averages `bits(x)` over
**the accepted ones only**, and adds `log2(accepted / trials)`.

Worth attacking:

- Is that derivation right, and is the estimator actually unbiased? I know of one
  soft spot already: `log2(accepted/trials)` is a ratio estimator inside a log,
  which is slightly biased for small samples. I believe it's negligible at the
  sample sizes used. I have not proved it.
- `build()` accumulates `bits` as it goes, adding `log2(choices)` at each step.
  In syllables mode the number of choices depends on the previous syllable
  (a consonant-final rime restricts the next onset to 19 rather than 34). Is
  summing per-step `log2(choices)` the correct `-log2 p(x)` for that process?
- **Capitalisation is priced at zero bits.** `-c` capitalises every word by a
  fixed rule, so it adds nothing an attacker doesn't know. `tests/test_features.py`
  asserts this. Is that reasoning right?
- `crack_time()` assumes an offline attack at 1e12 guesses/sec against the
  password's *own structure* — i.e. the attacker knows you used this tool with
  these settings. Is that the right thing to show a user? Is it stated clearly
  enough in the README that it's a comparison figure, not a prediction?

## 2. The Entra banned-password implementation

**File:** `passgen/banned.py` · **Spec:**
[How Entra evaluates passwords](https://learn.microsoft.com/en-us/entra/identity/authentication/concept-password-ban-bad)

Both worked examples from Microsoft's documentation reproduce exactly
(`C0ntos0Blank12` → 4, rejected; `ContoS0Bl@nkf9!` → 5, accepted). Two data
points don't prove the general case.

- **Span selection is a guess.** When several banned terms fuzzy-match
  overlapping regions, Microsoft doesn't specify which wins. I take the longest
  match first, on the theory that consuming more characters yields a lower score
  and is therefore the stricter reading. Is that actually the conservative
  direction in every case?
- **`_within_one_edit()`** implements edit distance ≤ 1 by hand rather than a
  general Levenshtein. Does it handle every insertion/deletion/substitution case,
  including at string boundaries?
- **`_halves()` is a prefilter** that skips terms whose first or second half
  doesn't appear literally in the password. The pigeonhole argument: with at most
  one edit, one half must survive intact. Is that sound? A false *negative* here
  silently fails to catch a banned password.
- Normalization implements only the four substitutions Microsoft documents
  (`0→o, 1→l, $→s, @→a`). Their docs say "such as", implying more exist. I chose
  not to invent extras. Agree or disagree?

## 3. Randomness isolation

**Files:** `passgen/cli.py`, `passgen/gui.py`

- Every password character should trace back to `secrets` (the OS CSPRNG).
- **`gui.py` imports `random`** — for the falling-code animation only. It's
  commented as such and I believe it's isolated, but "the password tool imports a
  non-cryptographic RNG" is exactly the thing to verify rather than take on
  trust. `grep -n "random" passgen/*.py` is a two-minute check.
- `secrets.choice` and `secrets.randbelow` are used directly, with no modulo
  arithmetic on top, so there should be no modulo bias. Worth confirming.

## 4. The word list — best use of fresh eyes, no expertise required

**File:** `passgen/wordlist.py` (1,779 words)

This is the weakest foundation in the project. I wrote it by hand, so it reflects
one person's judgement about what's typeable, and it has had no systematic pass.
The rules each word is meant to satisfy:

- 3–7 lowercase ASCII letters
- common enough to picture in your head
- spelled the way it sounds
- **no near-homophone pairs** (`flour`/`flower`, `their`/`there`) — if two words
  sound alike, someone hearing the password can't know which they were given
- nothing you'd wince at reading aloud to a client

Finding even a handful of violations is a real contribution. There's an open
issue about expanding it to ~4,000 words
([#1](https://github.com/Revg1794/passgen/issues/1)) — the size is a genuine
weakness too: 1,779 words is 10.8 bits/word against Diceware's 12.9.

## 5. Leaked-password checking

**File:** `passgen/leaked.py`

- Keys are the **first 8 bytes of SHA-1**, truncated to 64 bits. Across ten
  million entries that's roughly a 3-in-a-million chance of a collision. During
  generation a false positive is harmless (regenerate). But in `--check`, a
  collision would tell someone their password is breached when it isn't. Is that
  trade-off acceptable, and is 64 bits the right width?
- The on-disk format is little-endian with a byteswap on big-endian machines.
  Nobody has run this on a big-endian platform.

## 6. The GUI

**File:** `passgen/gui.py`

Lower stakes, but two behaviours are security-relevant and tested:

- the clipboard clears 30s after a copy, and **must not** clobber the clipboard
  if the user copied something else in the meantime
- `HIDE` masks passwords on screen while still copying the real value

`tests/test_gui.py` covers both, including a regression test for a real bug:
the first version of HIDE masked the list while the status bar underneath
spelled the password out in the NATO alphabet, which defeated the entire
feature. Worth checking whether anything else on screen still leaks while
masked.

## Untested assumptions

Things I believe but have not verified:

- ~~The `.exe` has never been run on a machine without Python installed.~~
  **Done, and it found a real bug.** v0.2.0's binary failed instantly with
  `No module named 'passgen'`: PyInstaller had bundled the entry stub without
  the application, and it passed locally only because that build ran in a venv
  where the package happened to be installed. Fixed in v0.2.1, which builds a
  console binary from the same bundle and runs it in CI, so an empty bundle now
  fails the release rather than the user. Re-verified on a clean Windows 11 VM.
  A reminder that "it worked on my machine" can be true and meaningless at the
  same time.
- The GUI has only been run on Windows. Tkinter behaviour on macOS and Linux is
  untested beyond the import.
- The release binary is unsigned. It carries a SHA-256 and a build provenance
  attestation (`gh attestation verify passgen.exe --repo Revg1794/passgen`), but
  SmartScreen will still warn.

## Not worth your time

The Matrix theme, the README prose, and the CLI flag names. Those are taste, and
I'll take opinions on them, but they aren't where a defect would hurt anyone.

## Reporting

Open an issue, or just tell Mike. If you find something in §1–§3, it's worth
raising even if you're not certain — "this looks wrong and here's why" is more
useful to me than silence, and I'd rather chase a false alarm than ship a real
one.

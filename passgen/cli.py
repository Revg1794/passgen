#!/usr/bin/env python3
"""passgen - random passwords a human can actually remember and type.

Two modes:
  words       (default) real words from a curated list:  CopperLemonDriftMask27#
  syllables   invented but pronounceable words:          TobiraKanpuVellon48$

Profiles (-p) target a specific platform's password rules and verify the result
against them before printing.

Randomness comes from `secrets` (the OS CSPRNG), never from `random`.
"""

import argparse
import math
import secrets
import sys

from . import banned
from . import leaked
from .wordlist import WORDS

# Pronounceable-nonsense building blocks: sounds that survive being read aloud
# over the phone and typed without hunting for keys.
SIMPLE_ONSETS = ("b", "ch", "d", "f", "g", "h", "j", "k", "l", "m", "n", "p",
                 "r", "s", "sh", "t", "v", "w", "z")
CLUSTER_ONSETS = ("br", "dr", "fl", "fr", "gl", "gr", "kr", "pl", "pr", "sk",
                  "sl", "sn", "sp", "st", "tr")
ONSETS = SIMPLE_ONSETS + CLUSTER_ONSETS
RIMES = ("a", "an", "ar", "e", "el", "en", "er", "i", "id", "il", "in", "ir",
         "o", "ol", "on", "or", "u", "un", "ur", "ay", "ee", "oo", "ow")
VOWELS = "aeiou"

# Separators chosen for reachability: no shift key, no numpad detour.
SEPARATORS = {"dash": "-", "dot": ".", "under": "_", "space": " ", "none": ""}

# Small symbol set - enough to satisfy a policy, few enough to recall which one.
# Every character here is accepted by Entra ID and on-prem AD.
SYMBOLS = "!?#$%&*+="

# Short names for --require, mapped to what categories() reports. Both the
# short and long spelling are accepted so "upper" and "uppercase" both work.
CATEGORIES = {"upper": "uppercase", "uppercase": "uppercase",
              "lower": "lowercase", "lowercase": "lowercase",
              "number": "number", "digit": "number",
              "symbol": "symbol", "special": "symbol"}

# Stand-in for "no --max-length given"; larger than any real policy ceiling.
NO_LIMIT = 10 ** 6

# Platform password rules. Sources are cited in README.md.
#   min/max      length bounds the platform enforces
#   categories   how many of lower/upper/digit/symbol the platform demands
PROFILES = {
    "entra": {
        "label": "Entra ID / Microsoft 365 cloud account",
        "min": 8, "max": 256, "categories": 3,
        "defaults": {"mode": "words", "words": 5, "capitalize": True, "digits": 2},
    },
    "msa": {
        "label": "Microsoft account (outlook.com / hotmail / live / Xbox)",
        "min": 8, "max": 16, "categories": 2,
        # 16 characters is a hard ceiling, so every character has to earn its
        # place. Three short invented words plus one digit and one symbol was
        # the best of six layouts measured (53 bits); it beats two longer words
        # on readability at the same strength, and the digit and symbol the
        # complexity policy demands pay for themselves in entropy.
        "defaults": {"mode": "syllables", "words": 3, "capitalize": True,
                     "digits": 1, "syllables": 2},
    },
    "ad": {
        "label": "on-prem Active Directory, default domain policy",
        "min": 7, "max": 127, "categories": 3,
        "defaults": {"mode": "words", "words": 5, "capitalize": True, "digits": 2},
    },
}


def make_words(count):
    return [secrets.choice(WORDS) for _ in range(count)], count * math.log2(len(WORDS))


def make_syllables(count, syllables):
    """Build pronounceable nonsense words. Returns (words, entropy_bits).

    A rime ending on a consonant is only ever followed by a single-consonant
    onset, so you get "Tobira" and "Kanpu" rather than "Brirdroo".
    """
    words, bits = [], 0.0
    for _ in range(count):
        chunks = []
        open_syllable = True
        for _ in range(syllables):
            onsets = ONSETS if open_syllable else SIMPLE_ONSETS
            rime = secrets.choice(RIMES)
            chunks.append(secrets.choice(onsets) + rime)
            open_syllable = rime[-1] in VOWELS
            bits += math.log2(len(onsets)) + math.log2(len(RIMES))
        words.append("".join(chunks))
    return words, bits


def build(args):
    """Generate one candidate. Returns (password, entropy_bits)."""
    if args.mode == "words":
        parts, bits = make_words(args.words)
    else:
        parts, bits = make_syllables(args.words, args.syllables)

    if args.capitalize:
        parts = [p.capitalize() for p in parts]  # fixed rule, so no added entropy

    sep = SEPARATORS[args.sep]
    password = sep.join(parts)

    if args.digits:
        password += sep + "".join(str(secrets.randbelow(10))
                                  for _ in range(args.digits))
        bits += args.digits * math.log2(10)

    if args.symbol:
        password += secrets.choice(SYMBOLS)
        bits += math.log2(len(SYMBOLS))

    return password, bits


def categories(password):
    """Which of Microsoft's four character categories the password hits."""
    found = set()
    for char in password:
        if char.islower():
            found.add("lowercase")
        elif char.isupper():
            found.add("uppercase")
        elif char.isdigit():
            found.add("number")
        else:
            found.add("symbol")
    return found


def acceptable(password, args):
    """True when the candidate clears every filter that's in force."""
    if not args.min_length <= len(password) <= args.max_length:
        return False
    if not args.require <= categories(password):
        return False
    if args.names and banned.substring_hit(password, args.names):
        return False
    if args.terms and banned.score(password, args.terms) < args.min_score:
        return False
    if args.leaked and args.leaked.lookup(password) is not None:
        return False
    return True


def generate(args, limit=10000):
    """Generate one password that passes every filter.

    Rejection sampling stays uniform over the passwords that do pass, so this
    biases nothing - it only shrinks the space, which `measure_entropy` prices in.
    """
    for _ in range(limit):
        password, bits = build(args)
        if acceptable(password, args):
            return password, bits
    raise SystemExit("passgen: " + diagnose(args, limit))


def diagnose(args, attempts, sample=500):
    """Explain which filter is blocking, so the error names the real cause."""
    blame = {"length": 0, "categories": 0, "names": 0, "banned": 0, "leaked": 0}
    for _ in range(sample):
        password = build(args)[0]
        if not args.min_length <= len(password) <= args.max_length:
            blame["length"] += 1
        if not args.require <= categories(password):
            blame["categories"] += 1
        if args.names and banned.substring_hit(password, args.names):
            blame["names"] += 1
        if args.terms and banned.score(password, args.terms) < args.min_score:
            blame["banned"] += 1
        if args.leaked and args.leaked.lookup(password) is not None:
            blame["leaked"] += 1

    culprit, hits = max(blame.items(), key=lambda item: item[1])
    hint = {
        "length": (f"no candidate fit {args.min_length}-{args.max_length} "
                   "characters. Try fewer words or shorter syllables"),
        "categories": (f"no candidate contained {', '.join(sorted(args.require))}. "
                       "Add -c for uppercase, -d N for numbers, --symbol for a "
                       "symbol, or drop the requirement from -r"),
        "names": ("every candidate contained one of the --name terms. Use "
                  "shorter names or a larger word count"),
        "banned": (f"no candidate scored {args.min_score} against the banned "
                   "terms. Use more words, or trim the banned list"),
        # If this one ever fires, the settings are generating from a space
        # smaller than the breach corpus. That is the real problem, not the list.
        "leaked": ("every candidate was in the leaked-password list, which "
                   "means these settings produce too few possible passwords. "
                   "Use more words rather than a smaller list"),
    }[culprit]
    return f"{hint} (tried {attempts:,} candidates)."


def measure_entropy(args, target=800, cap=500000):
    """Entropy of the passwords this configuration actually produces.

    Quoting one sample's bit count would be wrong twice over. In syllables mode
    the count is path-dependent (a consonant-final rime restricts the next onset
    to the 19 simple ones rather than all 34), and the length and banned-term
    filters discard candidates, which shrinks the space further.

    For a filter that keeps a share Z of an unfiltered distribution p, the
    filtered entropy is E_accepted[-log2 p(x)] + log2(Z) - the mean bits of the
    candidates that survive, less the bits the filter cost. Sampling runs until
    `target` candidates are accepted, so even the 16-character cap (which keeps
    well under 1%) converges instead of wobbling between runs.
    """
    accepted = trials = 0
    total_bits = 0.0
    while trials < cap and accepted < target:
        trials += 1
        password, bits = build(args)
        if acceptable(password, args):
            accepted += 1
            total_bits += bits
    if not accepted:
        return None
    return total_bits / accepted + math.log2(accepted / trials)


def compliance(password, profile):
    """Return a list of rule violations, empty when the password is acceptable."""
    problems = []
    if len(password) < profile["min"]:
        problems.append(f"shorter than {profile['min']} characters")
    if len(password) > profile["max"]:
        problems.append(f"longer than {profile['max']} characters")
    hit = categories(password)
    if len(hit) < profile["categories"]:
        problems.append(f"only {len(hit)} of the required {profile['categories']} "
                        f"character categories ({', '.join(sorted(hit))})")
    return problems


def strength(bits):
    if bits < 45:
        return "weak"
    if bits < 60:
        return "ok"
    if bits < 80:
        return "strong"
    return "very strong"


def crack_time(bits):
    """Rough offline-attack estimate: 1e12 guesses/sec, average is half the space."""
    seconds = (2 ** (bits - 1)) / 1e12
    for unit, size in (("seconds", 60), ("minutes", 60), ("hours", 24),
                       ("days", 365), ("years", 1000)):
        if seconds < size:
            label = unit[:-1] if f"{seconds:,.0f}" == "1" else unit
            return f"{seconds:,.0f} {label}"
        seconds /= size
    return f"{seconds:,.0f} millennia"


def parse_args(argv):
    p = argparse.ArgumentParser(
        prog="passgen",
        description="Generate random passwords that are easy to remember and type.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""examples:
  passgen                          5 words, a capital, digits and a symbol
  passgen -n 10                    ten candidates to choose from
  passgen -p entra                 meets Entra ID / Microsoft 365 rules
  passgen -p msa                   fits the 16-char consumer Microsoft cap
  passgen -p ad -w 6               on-prem AD, a little longer
  passgen -m syllables -w 3        invented words: TobiraKanpuVellon48$
  passgen -w 6 -s space            a spoken-friendly passphrase
  passgen -s dash -r ''            readable, no complexity requirement
  passgen --check                  audit an existing password
""")
    p.add_argument("-n", "--count", type=int, default=5,
                   help="how many passwords to print (default: 5)")
    p.add_argument("-p", "--profile", choices=sorted(PROFILES),
                   help="target a platform's rules and verify against them: "
                        + ", ".join(sorted(PROFILES)))
    p.add_argument("-w", "--words", type=int,
                   help="words per password (default: 5)")
    p.add_argument("-m", "--mode", choices=("words", "syllables"),
                   help="real words, or invented pronounceable ones (default: words)")
    p.add_argument("-s", "--sep", choices=sorted(SEPARATORS),
                   help="separator between words (default: none). Use -s dash "
                        "for readable passphrases where policy allows it")
    p.add_argument("--syllables", type=int,
                   help="syllables per invented word, syllables mode (default: 2)")
    p.add_argument("-d", "--digits", type=int, metavar="N",
                   help="append a block of N random digits")
    p.add_argument("-c", "--capitalize", action="store_true", default=None,
                   help="capitalize each word (on by default; it adds no "
                        "entropy, but keeps words legible without separators)")
    p.add_argument("-C", "--no-capitalize", dest="capitalize",
                   action="store_false",
                   help="lowercase words instead")
    p.add_argument("--symbol", action="store_true", default=None,
                   help="append one random symbol from "
                        + SYMBOLS.replace("%", "%%") + " (on by default)")
    p.add_argument("--no-symbol", dest="symbol", action="store_false",
                   help="omit the trailing symbol")
    p.add_argument("-r", "--require", metavar="LIST",
                   help="comma-separated character categories every password "
                        "must contain: upper, lower, number, symbol. Pass "
                        "-r '' to drop the requirement")
    p.add_argument("-b", "--banned-list", action="append", default=[],
                   metavar="FILE",
                   help="file of banned terms, one per line (# starts a "
                        "comment); repeatable")
    p.add_argument("--ban", action="append", default=[], metavar="TERM",
                   help="ban a single term inline; repeatable")
    p.add_argument("--name", action="append", default=[], metavar="TERM",
                   help="user or tenant name to substring-match and reject; "
                        "repeatable")
    p.add_argument("--min-score", type=int, default=banned.MIN_SCORE,
                   metavar="N",
                   help=f"Entra point score to require (default: "
                        f"{banned.MIN_SCORE})")
    p.add_argument("-l", "--leaked-list", metavar="FILE",
                   help="index of leaked passwords to reject, built with "
                        "tools/build_leaked_index.py (a plain password list "
                        "also works)")
    p.add_argument("--check", nargs="?", const="", metavar="PASSWORD",
                   help="audit an existing password instead of generating: "
                        "reports leak status, character categories and profile "
                        "compliance. Omit the value to be prompted, which keeps "
                        "the password out of your shell history")
    p.add_argument("--min-length", type=int, default=0, metavar="N",
                   help="reject candidates shorter than N characters")
    p.add_argument("--max-length", type=int, default=NO_LIMIT, metavar="N",
                   help="reject candidates longer than N characters. With -p "
                        "this can only tighten the platform's own limit, never "
                        "raise it")
    p.add_argument("-q", "--quiet", action="store_true",
                   help="print passwords only, no summary")

    args = p.parse_args(argv)

    # Precedence: an explicit flag beats the profile, which beats the built-in
    # default. Anything the user didn't type is still None at this point.
    profile = PROFILES[args.profile] if args.profile else None
    builtin = {"mode": "words", "words": 5, "capitalize": True,
               "digits": 2, "syllables": 2, "symbol": True, "sep": "none",
               "require": "upper,number,symbol"}
    for name, fallback in builtin.items():
        if getattr(args, name) is None:
            preset = profile["defaults"].get(name) if profile else None
            setattr(args, name, fallback if preset is None else preset)

    if profile:
        args.min_length = max(args.min_length, profile["min"])
        args.max_length = min(args.max_length, profile["max"])

    wanted = [c.strip().lower() for c in args.require.split(",") if c.strip()]
    unknown = sorted(set(wanted) - set(CATEGORIES))
    if unknown:
        p.error(f"unknown category {unknown[0]!r}; choose from "
                + ", ".join(sorted(CATEGORIES)))
    args.require = {CATEGORIES[c] for c in wanted}

    terms = list(args.ban)
    for path in args.banned_list:
        try:
            terms.extend(banned.load(path))
        except OSError as err:
            p.error(f"cannot read banned list {path}: {err.strerror}")
    args.terms = banned.prepare(terms)
    args.names = args.name

    args.leaked = None
    if args.leaked_list:
        try:
            args.leaked = leaked.load(args.leaked_list)
        except OSError as err:
            p.error(f"cannot read leaked list {args.leaked_list}: {err.strerror}")
        except ValueError as err:
            p.error(str(err))

    if min(args.count, args.words, args.syllables) < 1 or args.digits < 0:
        p.error("counts must be positive")
    if args.min_length > args.max_length:
        p.error("--min-length exceeds --max-length")
    return args


def audit(password, args):
    """Report on a password the user supplied. Returns (lines, ok)."""
    lines = [f"length: {len(password)} characters",
             "contains: " + ", ".join(sorted(categories(password)))]
    ok = True

    if args.leaked:
        hits = args.leaked.lookup(password)
        if hits is None:
            lines.append(f"not found in the {len(args.leaked):,}-entry "
                         "leaked-password list")
        else:
            ok = False
            times = "once" if hits == 1 else f"{hits:,} times"
            lines.append(f"BREACHED - appears {times} in the "
                         "leaked-password list. Do not use it.")
    else:
        lines.append("no leaked-password list supplied (-l); "
                     "breach status unknown")

    if args.terms:
        score = banned.score(password, args.terms)
        verdict = "passes" if score >= args.min_score else "FAILS"
        lines.append(f"banned-term score: {score} (need {args.min_score}) "
                     f"- {verdict}")
        ok = ok and score >= args.min_score

    if args.names:
        hit = banned.substring_hit(password, args.names)
        if hit:
            ok = False
            lines.append(f"contains the name or tenant term {hit!r}")

    if args.profile:
        profile = PROFILES[args.profile]
        problems = compliance(password, profile)
        if problems:
            ok = False
            lines.append(f"FAILS {profile['label']}: {'; '.join(problems)}")
        else:
            lines.append(f"meets {profile['label']}")

    return lines, ok


def check_mode(args):
    """Audit a password instead of generating. Exit status 1 means 'do not use'."""
    password = args.check
    if not password:
        import getpass
        password = getpass.getpass("password to check (not echoed): ")
    if not password:
        raise SystemExit("passgen: no password given")

    lines, ok = audit(password, args)
    for line in lines:
        print(line)
    return 0 if ok else 1


def main(argv=None):
    args = parse_args(argv)
    if args.check is not None:
        raise SystemExit(check_mode(args))
    profile = PROFILES[args.profile] if args.profile else None

    results = [generate(args) for _ in range(args.count)]
    for password, _ in results:
        print(password)

    if args.quiet:
        return

    bits = measure_entropy(args)
    if bits is None:  # every sample was rejected; generate() would have failed
        return

    source = (f"{len(WORDS):,}-word list" if args.mode == "words"
              else "invented syllables")
    # Summary goes to stderr so `passgen -q > file` stays clean.
    out = sys.stderr
    print(f"\n{bits:.0f} bits of entropy each - {strength(bits)} ({source})", file=out)
    print(f"~{crack_time(bits)} to crack offline at a trillion guesses/sec", file=out)

    if args.require:
        print("every password contains: " + ", ".join(sorted(args.require)),
              file=out)

    if args.terms or args.names:
        checks = []
        if args.terms:
            worst = min(banned.score(pw, args.terms) for pw, _ in results)
            plural = "" if len(args.terms) == 1 else "s"
            checks.append(f"{len(args.terms)} banned term{plural}, worst score "
                          f"{worst} (need {args.min_score})")
        if args.names:
            plural = "" if len(args.names) == 1 else "s"
            checks.append(f"{len(args.names)} name/tenant substring{plural}")
        print("checked against " + " and ".join(checks), file=out)

    if profile:
        failures = [tuple(compliance(pw, profile)) for pw, _ in results]
        broken = [f for f in failures if f]
        if broken:
            print(f"WARNING - does not meet {profile['label']}: "
                  f"{'; '.join(broken[0])}", file=out)
        else:
            print(f"meets {profile['label']} "
                  f"({profile['min']}-{profile['max']} chars, "
                  f"{profile['categories']} of 4 character categories)", file=out)


if __name__ == "__main__":
    main()

"""Microsoft Entra Password Protection's banned-password check.

Implements the evaluation algorithm Microsoft documents in
https://learn.microsoft.com/en-us/entra/identity/authentication/concept-password-ban-bad
so passgen can reject a candidate locally instead of finding out at the
password-change prompt:

  1. Normalize: lowercase, then common character substitutions.
  2. Fuzzy match every banned term against the normalized password at an edit
     distance of 1.
  3. Score: one point per banned term found, one point per remaining character.
     Fewer than five points is rejected.

Two caveats worth knowing, both documented upstream:

  * Microsoft deliberately does not publish the global banned list, so this
    checks only the terms you supply. It cannot tell you a password is safe -
    only that it does not trip on *your* terms.
  * The substitution table is published as an example ("such as"), not as a
    complete list, and Microsoft reserves the right to change the algorithm.
"""

import unicodedata

# The four substitutions Microsoft documents. Deliberately not extended with
# guessed leetspeak: inventing extra ones would reject passwords Entra accepts,
# and would not catch the ones it actually rejects.
SUBSTITUTIONS = {"0": "o", "1": "l", "$": "s", "@": "a"}

# Entra's custom banned list only accepts terms of 4-16 characters, and
# substring matching is documented as applying only to terms of 4 or more.
MIN_TERM = 4
MAX_TERM = 16

# "A password must be at least five (5) points to be accepted."
MIN_SCORE = 5


def normalize(password):
    """Lowercase, then apply the documented character substitutions."""
    lowered = unicodedata.normalize("NFKC", password).lower()
    return "".join(SUBSTITUTIONS.get(char, char) for char in lowered)


def _within_one_edit(candidate, term):
    """True when candidate is reachable from term by at most one edit."""
    short, long_ = sorted((candidate, term), key=len)
    if len(long_) - len(short) > 1:
        return False

    if len(short) == len(long_):  # substitution only
        return sum(a != b for a, b in zip(short, long_)) <= 1

    i = j = 0  # one insertion/deletion: walk both, allowing a single skip
    skipped = False
    while i < len(short) and j < len(long_):
        if short[i] == long_[j]:
            i += 1
            j += 1
        elif skipped:
            return False
        else:
            skipped = True
            j += 1
    return True


def _halves(term):
    """Split a term in two. With at most one edit, one half must survive intact.

    That makes an exact-substring test on either half a sound prefilter: it can
    never discard a real match, and it skips the expensive scan for the ~99% of
    terms that cannot possibly match.
    """
    middle = len(term) // 2
    return term[:middle], term[middle:]


def prepare(terms):
    """Normalize and dedupe terms, pairing each with its prefilter halves."""
    prepared = {}
    for term in terms:
        clean = normalize(term.strip())
        if MIN_TERM <= len(clean) <= MAX_TERM:
            prepared[clean] = _halves(clean)
    return sorted((term, halves) for term, halves in prepared.items())


def _spans(normalized, prepared):
    """Every (start, end) where a banned term fuzzy-matches, longest first."""
    hits = []
    for term, (head, tail) in prepared:
        if head not in normalized and tail not in normalized:
            continue
        size = len(term)
        for length in (size - 1, size, size + 1):
            for start in range(len(normalized) - length + 1):
                if _within_one_edit(normalized[start:start + length], term):
                    hits.append((start, start + length))
    # Longest match first minimizes the score, which is the strict reading.
    return sorted(hits, key=lambda span: (span[0] - span[1], span[0]))


def score(password, prepared):
    """Entra's point score: one per banned term, one per leftover character."""
    normalized = normalize(password)
    consumed = set()
    points = 0

    for start, end in _spans(normalized, prepared):
        if consumed.isdisjoint(range(start, end)):
            consumed.update(range(start, end))
            points += 1  # the banned term itself is worth exactly one point

    return points + (len(normalized) - len(consumed))


def substring_hit(password, names):
    """Names and tenant terms match as plain substrings, not fuzzily."""
    normalized = normalize(password)
    for name in names:
        clean = normalize(name.strip())
        if len(clean) >= MIN_TERM and clean in normalized:
            return clean
    return None


def load(path):
    """Read a banned-terms file: one term per line, # starts a comment."""
    terms = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            term = line.split("#", 1)[0].strip()
            if term:
                terms.append(term)
    return terms

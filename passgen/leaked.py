"""Checking passwords against a locally built index of leaked passwords.

Worth being clear about what this is for. passgen generates from a space of
roughly 1.8e19 passwords at the default settings, and breach corpora hold on the
order of a billion entries, so a *generated* password lands in one about once
every eighteen billion runs. This is not a safety net for normal output.

It earns its place in two other ways:

  * As a canary for misconfiguration. Dial the settings down far enough
    (`-w 2 -r ''` is about 22 bits) and you are generating from a space smaller
    than the breach corpus, where collisions stop being theoretical.
  * As an audit tool for passwords a human chose, via `--check`, which is the
    case that actually comes up.

Matching is exact. That is deliberate and differs from `banned.py`, which does
Entra's fuzzy base-term matching: "within one edit of a leaked password" is both
meaningless and computationally hopeless at this scale.

Index format, all little-endian:

    magic  b"PGLK"        4 bytes
    version              1 byte
    reserved             3 bytes
    count                4 bytes, unsigned
    keys                 count * 8 bytes, sorted ascending
    counts               count * 4 bytes, parallel to keys

The key is the first 8 bytes of the password's SHA-1. Truncating to 64 bits
gives a collision chance of roughly three in a million across ten million
entries, which is far below the rate at which the underlying data is wrong.
"""

import array
import bisect
import hashlib
import struct
import sys

MAGIC = b"PGLK"
VERSION = 1
_HEADER = struct.Struct("<4sB3xI")

# Truncated-hash width and the array typecodes that must match it.
_KEY_CODE = "Q"
_COUNT_CODE = "I"


def digest(password):
    """The 64-bit key for a password: the first 8 bytes of its SHA-1."""
    raw = hashlib.sha1(password.encode("utf-8")).digest()
    return int.from_bytes(raw[:8], "big")


def key_from_hex(sha1_hex):
    """The same key, from a hex SHA-1 as found in HIBP's published files."""
    return int(sha1_hex[:16], 16)


def _new(code):
    values = array.array(code)
    expected = 8 if code == _KEY_CODE else 4
    if values.itemsize != expected:
        raise RuntimeError(
            f"array typecode {code!r} is {values.itemsize} bytes, not {expected}; "
            "this platform needs a different index implementation")
    return values


class Index:
    """A sorted key array plus parallel occurrence counts."""

    def __init__(self, keys, counts):
        self.keys = keys
        self.counts = counts

    def __len__(self):
        return len(self.keys)

    def lookup(self, password):
        """Occurrence count if the password is in the index, else None."""
        key = digest(password)
        position = bisect.bisect_left(self.keys, key)
        if position < len(self.keys) and self.keys[position] == key:
            return self.counts[position]
        return None

    def save(self, path):
        keys, counts = self.keys, self.counts
        if sys.byteorder != "little":  # the format is little-endian on disk
            keys, counts = _copy(keys), _copy(counts)
            keys.byteswap()
            counts.byteswap()
        with open(path, "wb") as handle:
            handle.write(_HEADER.pack(MAGIC, VERSION, len(self.keys)))
            keys.tofile(handle)
            counts.tofile(handle)


def _copy(values):
    duplicate = _new(values.typecode)
    duplicate.extend(values)
    return duplicate


def from_pairs(pairs):
    """Build an index from (key, count) pairs. Sorts and de-duplicates."""
    best = {}
    for key, count in pairs:
        if count > best.get(key, 0):
            best[key] = count
    keys = _new(_KEY_CODE)
    counts = _new(_COUNT_CODE)
    for key in sorted(best):
        keys.append(key)
        # Counts are capped rather than allowed to overflow the 32-bit field.
        counts.append(min(best[key], 0xFFFFFFFF))
    return Index(keys, counts)


def load_index(path):
    """Read a prebuilt binary index."""
    with open(path, "rb") as handle:
        magic, version, count = _HEADER.unpack(handle.read(_HEADER.size))
        if magic != MAGIC:
            raise ValueError(f"{path} is not a passgen leaked-password index")
        if version != VERSION:
            raise ValueError(f"{path} is index version {version}, expected {VERSION}")
        keys = _new(_KEY_CODE)
        counts = _new(_COUNT_CODE)
        keys.fromfile(handle, count)
        counts.fromfile(handle, count)
    if sys.byteorder != "little":
        keys.byteswap()
        counts.byteswap()
    return Index(keys, counts)


def load_plaintext(path):
    """Read a newline-delimited password list, or HIBP's `SHA1:count` format."""
    pairs = []
    with open(path, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.rstrip("\r\n")
            if not line:
                continue
            head, separator, tail = line.partition(":")
            if separator and len(head) == 40 and _is_hex(head):
                count = int(tail) if tail.strip().isdigit() else 1
                pairs.append((key_from_hex(head), count))
            else:
                pairs.append((digest(line), 1))
    return from_pairs(pairs)


def _is_hex(text):
    try:
        int(text, 16)
    except ValueError:
        return False
    return True


def load(path):
    """Load either a prebuilt index or a raw list, detected by content."""
    with open(path, "rb") as handle:
        is_index = handle.read(len(MAGIC)) == MAGIC
    return load_index(path) if is_index else load_plaintext(path)

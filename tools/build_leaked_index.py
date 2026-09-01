#!/usr/bin/env python3
"""Turn a breach corpus into a compact index passgen can query offline.

Accepts either format:

  * Have I Been Pwned's published files - `SHA1HASH:occurrences` per line.
  * A plain list - one password per line, hashed here.

The full HIBP corpus is around a billion entries and roughly 8 GB as an index,
which is not a sensible thing to load on every run. The top few million by
occurrence count covers essentially all real-world password spraying, so
`--top` keeps only the most common entries and is what you usually want.

Examples:

    # Ten million most-common entries from the HIBP download
    python tools/build_leaked_index.py pwned-passwords-sha1.txt leaked.idx --top 10000000

    # A small plaintext list, kept whole
    python tools/build_leaked_index.py rockyou.txt rockyou.idx
"""

import argparse
import heapq
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from passgen import leaked


def parse_line(line):
    """Return (key, count) for a line, or None if it holds nothing useful."""
    line = line.rstrip("\r\n")
    if not line:
        return None
    head, separator, tail = line.partition(":")
    if separator and len(head) == 40:
        try:
            key = leaked.key_from_hex(head)
        except ValueError:
            return None  # not actually a hash; treat the line as a password
        return key, int(tail) if tail.strip().isdigit() else 1
    return leaked.digest(line), 1


def read_pairs(path, top, progress):
    """Stream the source, keeping either everything or the `top` most common.

    heapq.nsmallest-style selection keeps memory at O(top) rather than O(file),
    which matters when the source is a 38 GB text file.
    """
    kept = []  # min-heap of (count, key), so the least common falls off first
    everything = []
    seen = 0
    with open(path, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            parsed = parse_line(line)
            if parsed is None:
                continue
            key, count = parsed
            seen += 1
            if top:
                if len(kept) < top:
                    heapq.heappush(kept, (count, key))
                elif count > kept[0][0]:
                    heapq.heapreplace(kept, (count, key))
            else:
                everything.append((key, count))
            if progress and seen % 5_000_000 == 0:
                print(f"  read {seen:,} entries...", file=sys.stderr)
    if top:
        return [(key, count) for count, key in kept], seen
    return everything, seen


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Build a passgen leaked-password index.")
    parser.add_argument("source", help="HIBP SHA1:count file, or a password list")
    parser.add_argument("output", help="index file to write")
    parser.add_argument("--top", type=int, default=0, metavar="N",
                        help="keep only the N most common entries "
                             "(default: keep everything)")
    parser.add_argument("-q", "--quiet", action="store_true")
    args = parser.parse_args(argv)

    if not args.quiet:
        print(f"reading {args.source}...", file=sys.stderr)
    pairs, seen = read_pairs(args.source, args.top, not args.quiet)

    index = leaked.from_pairs(pairs)
    index.save(args.output)

    if not args.quiet:
        size = os.path.getsize(args.output)
        print(f"read {seen:,} entries, wrote {len(index):,} to {args.output} "
              f"({size / 1_048_576:.1f} MB)", file=sys.stderr)
        print(f"use it with: passgen --leaked-list {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Generate all FCC915 ELRS 4.x FHSS classes using the public Python model."""
from __future__ import annotations

import argparse
import hashlib
import pathlib

from h44fa_reconstruct import generate_fhss, seed_from


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=pathlib.Path)
    parser.add_argument("--uid4", type=lambda value: int(value, 0), default=0x56)
    parser.add_argument("--uid5", type=lambda value: int(value, 0), default=0x78)
    args = parser.parse_args()
    if not 0 <= args.uid4 <= 0xFF or not 0 <= args.uid5 <= 0xFF:
        parser.error("UID bytes must be in 0..255")

    digest = hashlib.sha256()
    count = 0
    with args.output.open("wb") as output:
        for uid2_low7 in range(0x80):
            for uid3 in range(0x100):
                row = bytes(generate_fhss(seed_from(uid2_low7, uid3, args.uid4, args.uid5)))
                output.write(row)
                digest.update(row)
                count += len(row)
    print(f"ELRS41_PYTHON_MATRIX_BYTES={count}")
    print(f"ELRS41_PYTHON_MATRIX_SHA256={digest.hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

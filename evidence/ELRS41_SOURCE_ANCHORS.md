# ExpressLRS 4.1 Exhaustive-Validation Source Anchors

- upstream repository: `https://github.com/ExpressLRS/ExpressLRS`;
- tag: `4.1.0`;
- exact commit: `a9d4a9cb5b5687c4c9d7e9e7fbdf44ad93651da6`;
- domain: FCC915; logical radio: SX127X; OTA version: 4;
- search space: 32,768 canonical UID2[6:0]/UID3 classes;
- sequence length: 240 positions per class;
- total: 7,864,320 positions compared per implementation;
- mismatches: zero;
- matrix SHA-256:
  `a82024c1f89fcde103406c633fa8495b0bd6cea50c5762ef5cd51d8eb02ff303`.

`ELRS41_EXHAUSTIVE_VALIDATION.json` is a sanitized public selection from the
original validation report. The JSON retains the SHA-256 digest of that private
original while omitting local paths and its absolute timestamp.
`scripts/verify_elrs41_evidence.py` validates the internal consistency and
cryptographic anchors of the public selection.
`scripts/replay_elrs41_upstream.sh` additionally rebuilds the matrix from a
local checkout of the exact upstream commit and compares it with the
distributed Python implementation.

This validation is entirely offline: it builds no embedded firmware, accesses
no radio, and performs no RF transmission.

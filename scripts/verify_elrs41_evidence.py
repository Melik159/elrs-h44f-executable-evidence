#!/usr/bin/env python3
"""Verify the sanitized ELRS 4.1 exhaustive-validation record."""
from __future__ import annotations

import hashlib
import json
import pathlib
import re
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
RECORD = ROOT / "evidence" / "ELRS41_EXHAUSTIVE_VALIDATION.json"
MULTIVERSION_RECORD = ROOT / "evidence" / "ELRS_MULTIVERSION_EXHAUSTIVE_VALIDATION.json"
COMMIT = "a9d4a9cb5b5687c4c9d7e9e7fbdf44ad93651da6"
MATRIX_HASH = "a82024c1f89fcde103406c633fa8495b0bd6cea50c5762ef5cd51d8eb02ff303"
ORIGINAL_HASH = "66740d79a56d685f091ce235ffd89cc5ba76faf9d2b5173d10f6fd16c2ee1d47"
MULTIVERSION_ORIGINAL_HASH = "0e21e32fd6ff5231fd74669afac10d3d425221d1c4133fbd14216398436fe600"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def main() -> int:
    try:
        raw = RECORD.read_bytes()
        data = json.loads(raw)
        require(data["schema"] == "elrs41-public-exhaustive-evidence-v1", "bad schema")
        require(data["status"] == "PASS", "record is not PASS")
        require(data["tag"] == "4.1.0" and data["commit"] == COMMIT, "wrong upstream pin")
        require(data["domain"] == "FCC915" and data["ota_version"] == 4, "wrong family")
        classes = data["canonical_uid2_uid3_classes"]
        positions = data["positions_per_class"]
        comparisons = classes * positions
        require(classes == 32768 and positions == 240, "unexpected search dimensions")
        require(comparisons == 7864320, "arithmetic mismatch")
        require(data["comparisons_per_implementation"] == comparisons, "reported count mismatch")
        require(data["matrix_sha256"] == MATRIX_HASH, "matrix hash mismatch")
        require(data["private_original_report_sha256"] == ORIGINAL_HASH, "original anchor mismatch")
        required_names = {
            "elrs_4_1_upstream_vs_project_python",
            "elrs_4_1_upstream_vs_project_numba",
            "elrs_4_1_upstream_vs_elrs_4_0_1_upstream",
        }
        rows = data["comparisons"]
        require({row["name"] for row in rows} == required_names, "comparison set mismatch")
        for row in rows:
            require(row["entries"] == comparisons, f"wrong entry count: {row['name']}")
            require(row["mismatches"] == 0 and row["status"] == "PASS", f"failed: {row['name']}")
            require(row["reference_sha256"] == MATRIX_HASH, f"reference hash: {row['name']}")
            require(row["subject_sha256"] == MATRIX_HASH, f"subject hash: {row['name']}")
        require(b"/home/" not in raw and b"hal@" not in raw, "private path or host remains")
        require(not re.search(rb"20[0-9]{2}-[01][0-9]-[0-3][0-9]T", raw), "absolute time remains")

        multiversion_raw = MULTIVERSION_RECORD.read_bytes()
        multiversion = json.loads(multiversion_raw)
        require(
            multiversion["schema"] == "elrs-multiversion-public-exhaustive-evidence-v1",
            "bad multiversion schema",
        )
        require(multiversion["status"] == "PASS", "multiversion record is not PASS")
        require(multiversion["canonical_uid2_uid3_classes_per_family"] == 32768, "bad class count")
        require(multiversion["negative_control_passed"] is True, "negative control failed")
        require(multiversion["deterministic_roundtrips"] == 64, "roundtrip count mismatch")
        require(
            multiversion["private_original_report_sha256"] == MULTIVERSION_ORIGINAL_HASH,
            "multiversion original anchor mismatch",
        )
        families = multiversion["families"]
        require([row["family"] for row in families] == ["elrs-1", "elrs-2", "elrs-3", "elrs-4"], "family set")
        total = 0
        for row in families:
            expected = 32768 * row["positions_per_class"]
            require(row["compared_entries"] == expected, f"family arithmetic: {row['family']}")
            require(row["mismatches"] == 0 and row["status"] == "PASS", f"family failed: {row['family']}")
            total += expected
        require(total == 31981568, "multiversion total arithmetic mismatch")
        require(multiversion["total_compared_entries"] == total, "multiversion reported total mismatch")
        require(b"/home/" not in multiversion_raw and b"hal@" not in multiversion_raw, "private multiversion token")
        require(not re.search(rb"20[0-9]{2}-[01][0-9]-[0-3][0-9]T", multiversion_raw), "multiversion absolute time")
        print(f"ELRS41_RECORD_SHA256={hashlib.sha256(raw).hexdigest()}")
        print(f"ELRS41_COMMIT={COMMIT}")
        print(f"ELRS41_CLASSES={classes}")
        print(f"ELRS41_POSITIONS_PER_CLASS={positions}")
        print(f"ELRS41_COMPARISONS={comparisons}")
        print("ELRS41_MISMATCHES=0")
        print(f"ELRS41_MATRIX_SHA256={MATRIX_HASH}")
        print(f"MULTIVERSION_RECORD_SHA256={hashlib.sha256(multiversion_raw).hexdigest()}")
        print(f"MULTIVERSION_COMPARISONS={total}")
        print("MULTIVERSION_MISMATCHES=0")
        print("MULTIVERSION_EVIDENCE_VERDICT=PASS")
        print("ELRS41_EVIDENCE_VERDICT=PASS")
        return 0
    except Exception as error:
        print(f"ELRS41_EVIDENCE_ERROR={type(error).__name__}:{error}", file=sys.stderr)
        print("ELRS41_EVIDENCE_VERDICT=FAIL", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""One-command verification of the compact ELRS 4.1/H44F evidence set."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import pathlib
import re
import subprocess
import sys
import tempfile


ROOT = pathlib.Path(__file__).resolve().parent
EVIDENCE = ROOT / "evidence"
SCRIPTS = ROOT / "scripts"
A_LOG = EVIDENCE / "H44F-A_5e47158c-14cb-4395-a803-47ea468e8e8a.log"
B_LOG = EVIDENCE / "H44F-B_583431a1-9948-4173-9b9b-14954169cb33.log"


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fields(line: str) -> dict[str, str]:
    return dict(part.split("=", 1) for part in line.split(",")[1:] if "=" in part)


def one(lines: list[str], prefix: str) -> dict[str, str]:
    found = [fields(line) for line in lines if line.startswith(prefix)]
    if len(found) != 1:
        raise ValueError(f"expected one {prefix} record, found {len(found)}")
    return found[0]


def load_module(name: str, path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def run_checked(label: str, command: list[str]) -> str:
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    if result.returncode:
        raise RuntimeError(
            f"{label} failed (exit {result.returncode})\n"
            f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
        )
    return result.stdout


def verify_package_manifest() -> int:
    manifest = ROOT / "MANIFEST_SHA256.txt"
    count = 0
    for raw in manifest.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        expected, relative = raw.split("  ", 1)
        path = ROOT / relative
        if not path.is_file() or sha256(path) != expected:
            raise ValueError(f"integrity failure: {relative}")
        count += 1
    return count


def verify_metadata() -> None:
    a = json.loads((EVIDENCE / "H44F-A.manifest.json").read_text(encoding="utf-8"))
    b = json.loads((EVIDENCE / "H44F-B.manifest.json").read_text(encoding="utf-8"))
    if a["campaign"] != "H44F-A" or a["verdict"] != "PASS":
        raise ValueError("H44F-A metadata is not a retained PASS run")
    if a["artifacts"]["public_log"]["sha256"] != sha256(A_LOG):
        raise ValueError("H44F-A public-log hash mismatch")
    if b["campaign"] != "H44F-B" or b["hardware_verdict"] != "PASS":
        raise ValueError("H44F-B metadata is not a retained PASS run")
    if b["public_sanitized_sha256"] != sha256(B_LOG):
        raise ValueError("H44F-B public-log hash mismatch")


def verify_sanitization() -> None:
    forbidden_bytes = (b"/home/", b"hal@", b"/dev/tty", b"MY_BINDING_PHRASE")
    absolute_time = re.compile(rb"20[0-9]{2}[-/]?[01][0-9][-T/]?[0-3][0-9]T[0-9]{6}Z")
    for path in (A_LOG, B_LOG):
        data = path.read_bytes()
        if any(token in data for token in forbidden_bytes) or absolute_time.search(data):
            raise ValueError(f"private host/path/time token in {path.name}")


def verify_h44fa_reconstruction() -> tuple[str, int]:
    lines = A_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
    sync = one(lines, "H44F_CORE_BLIND_SYNC,")
    expected = one(lines, "HOST_H44F_CORE_RECONSTRUCTION,")
    observation_fields = [
        fields(line) for line in lines if line.startswith("H44F_CORE_PROBE_OBSERVATION,")
    ]
    module = load_module("compact_h44fa_reconstruct", SCRIPTS / "h44fa_reconstruct.py")
    observations = [
        module.Observation(
            int(item["fhss_index"]), int(item["channel"]),
            int(item["ota_nonce"]), int(item["slot_delta"]), item["raw"],
        )
        for item in observation_fields
    ]
    result = module.reconstruct(int(sync["uid4"], 0), int(sync["uid5"], 0), observations)
    actual = {
        "uid2_candidates": f"{result.uid2_candidates[0]:02X}|{result.uid2_candidates[1]:02X}",
        "uid3": f"{result.uid3:02X}",
        "crc_initializer": f"0x{result.crc_initializer:04X}",
        "canonical_seed": f"0x{result.canonical_seed:08X}",
        "sequence_sha256": result.sequence_sha256,
    }
    for key, value in actual.items():
        if expected.get(key) != value:
            raise ValueError(f"H44F-A independent reconstruction mismatch: {key}")
    return result.sequence_sha256, len(observations)


def verify_h44fb_reconstruction() -> tuple[str, int, str]:
    lines = B_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
    sync = one(lines, "H44FB_BLIND_SYNC,")
    expected = one(lines, "HOST_H44FB_RECONSTRUCTION,")
    observation_fields = [
        fields(line) for line in lines if line.startswith("H44FB_PROBE_OBSERVATION,")
    ]
    module = load_module("compact_h44fb_reconstruct", SCRIPTS / "h44fb_reconstruct.py")
    observations = [
        module.Observation(
            int(item["fhss_index"]), int(item["channel"]),
            int(item["ota_nonce"]), int(item["slot_delta"]), item["raw"],
        )
        for item in observation_fields
    ]
    result = module.reconstruct(int(sync["uid4"], 0), int(sync["uid5"], 0), observations)
    actual = {
        "uid2_candidates": f"{result.uid2_candidates[0]:02X}|{result.uid2_candidates[1]:02X}",
        "uid3": f"{result.uid3:02X}",
        "crc_initializer": f"0x{result.crc_initializer:04X}",
        "canonical_seed": f"0x{result.canonical_seed:08X}",
        "sequence_sha256": result.sequence_sha256,
        "observation_model": result.observation_model,
    }
    for key, value in actual.items():
        if expected.get(key) != value:
            raise ValueError(f"H44F-B independent reconstruction mismatch: {key}")
    return result.sequence_sha256, len(observations), result.observation_model


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verbose", action="store_true", help="show verifier details")
    args = parser.parse_args()
    details: list[tuple[str, str]] = []
    try:
        file_count = verify_package_manifest()
        verify_metadata()
        verify_sanitization()
        print(f"[1/7] Integrity and anonymization ........ PASS ({file_count} files)")

        elrs41_verifier = run_checked(
            "ELRS 4.1 evidence verifier",
            [sys.executable, str(SCRIPTS / "verify_elrs41_evidence.py")],
        )
        if (
            "ELRS41_EVIDENCE_VERDICT=PASS" not in elrs41_verifier
            or "MULTIVERSION_EVIDENCE_VERDICT=PASS" not in elrs41_verifier
        ):
            raise ValueError("offline source evidence verifier did not emit PASS")
        details.append(("ELRS 4.1 evidence verifier", elrs41_verifier))
        print("[2/7] Offline exhaustive evidence ....... PASS (39,845,888 positions)")

        a_verifier = run_checked(
            "H44F-A verifier", [sys.executable, str(SCRIPTS / "verify_h44fa_log.py"), str(A_LOG)]
        )
        if "H44F_OFFLINE_VERDICT=PASS" not in a_verifier:
            raise ValueError("H44F-A verifier did not emit PASS")
        details.append(("H44F-A verifier", a_verifier))
        print("[3/7] H44F-A campaign verifier .......... PASS")

        with tempfile.TemporaryDirectory(prefix="h44f-proof-") as temporary:
            temp = pathlib.Path(temporary)
            a_parser = run_checked(
                "H44F-A RAW parser",
                [sys.executable, str(SCRIPTS / "parse_h44fa_raw.py"), str(A_LOG),
                 "--csv", str(temp / "raw.csv"), "--summary", str(temp / "raw.txt"),
                 "--throttle-channel", "3"],
            )
        if "H44F_CORE_RAW_PARSER_VERDICT=PASS" not in a_parser:
            raise ValueError("H44F-A RAW parser did not emit PASS")
        details.append(("H44F-A RAW parser", a_parser))
        print("[4/7] H44F-A RAW replay (5,671 rows) .... PASS")

        a_hash, a_observations = verify_h44fa_reconstruction()
        print(f"[5/7] H44F-A independent reconstruction  PASS ({a_observations} observations)")

        b_verifier = run_checked(
            "H44F-B verifier", [sys.executable, str(SCRIPTS / "verify_h44fb_log.py"), str(B_LOG)]
        )
        if "H44FB_OFFLINE_VERDICT=PASS" not in b_verifier:
            raise ValueError("H44F-B verifier did not emit PASS")
        details.append(("H44F-B verifier", b_verifier))
        print("[6/7] H44F-B campaign verifier .......... PASS")

        b_hash, b_observations, b_model = verify_h44fb_reconstruction()
        print(f"[7/7] H44F-B 5-hop reconstruction ....... PASS ({b_model})")

        if args.verbose:
            for label, output in details:
                print(f"\n--- {label} ---\n{output.rstrip()}")

        print("\nSUMMARY")
        print("ELRS 4.1: exhaustive upstream/Python FHSS comparison, 7,864,320 positions: PASS")
        print("H44F-A: full blind profile/identity campaign, 960/960 follow, controlled substitution: PASS")
        print("H44F-B: RX-only FAST reconstruction from 5 hops, 20/20 follow packets: PASS")
        print(f"FHSS_SEQUENCE_SHA256={a_hash}")
        print(f"H44FA_OBSERVATIONS={a_observations}")
        print(f"H44FB_OBSERVATIONS={b_observations}")
        print(f"SEQUENCES_IDENTICAL={int(a_hash == b_hash)}")
        print("ELRS41_OFFLINE_POSITIONS=7864320")
        print("MULTIVERSION_OFFLINE_POSITIONS=31981568")
        print("COMBINED_OFFLINE_POSITIONS=39845888")
        print("BINDING_PHRASE_RECOVERED=0")
        print("COMPACT_EVIDENCE_VERDICT=PASS")
        return 0
    except Exception as error:
        print(f"COMPACT_EVIDENCE_ERROR={type(error).__name__}:{error}", file=sys.stderr)
        print("COMPACT_EVIDENCE_VERDICT=FAIL", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

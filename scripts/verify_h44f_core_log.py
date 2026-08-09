#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import pathlib


def fields(line: str) -> dict[str, str]:
    return dict(part.split("=", 1) for part in line.split(",")[1:] if "=" in part)


def records(lines: list[str], prefix: str) -> list[str]:
    """Return exact records, allowing only non-identifier serial noise before them.

    This deliberately rejects a substring match such as H44F_CORE_RECONSTRUCTION inside
    HOST_H44F_CORE_RECONSTRUCTION.
    """
    out: list[str] = []
    for line in lines:
        start = 0
        while True:
            index = line.find(prefix, start)
            if index < 0:
                break
            if index == 0 or not (line[index - 1].isalnum() or line[index - 1] == "_"):
                out.append(line[index:])
                break
            start = index + 1
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("log")
    args = parser.parse_args()
    path = pathlib.Path(args.log)
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    checks: list[tuple[str, bool]] = []

    def one(prefix: str) -> str | None:
        found = records(lines, prefix)
        checks.append((f"single_{prefix.rstrip(',').lower()}", len(found) == 1))
        return found[0] if len(found) == 1 else None

    host_line = one("HOST_H44F_CORE_SESSION,")
    boot_line = one("H44F_CORE_BOOT,")
    profile_line = one("H44F_CORE_PROFILE_READ_ONLY,")
    sync_line = one("H44F_CORE_BLIND_SYNC,")
    probe_line = one("H44F_CORE_BLIND_PROBE,")
    host_recon_line = one("HOST_H44F_CORE_RECONSTRUCTION,")
    recon_line = one("H44F_CORE_RECONSTRUCTION,")
    follow_line = one("H44F_CORE_FHSS_FOLLOW,")
    fresh_line = one("H44F_CORE_FRESH_SYNC,")
    off_line = one("H44F_CORE_OPERATOR_AERIS_OFF,")
    tx_line = one("H44F_CORE_TX,")
    raw_line = one("H44F_CORE_RAW_CAPTURE,")
    result_line = one("H44F_CORE_RESULT,")

    host = fields(host_line) if host_line else {}
    boot = fields(boot_line) if boot_line else {}
    profile = fields(profile_line) if profile_line else {}
    sync = fields(sync_line) if sync_line else {}
    probe = fields(probe_line) if probe_line else {}
    host_recon = fields(host_recon_line) if host_recon_line else {}
    recon = fields(recon_line) if recon_line else {}
    follow = fields(follow_line) if follow_line else {}
    fresh = fields(fresh_line) if fresh_line else {}
    off = fields(off_line) if off_line else {}
    tx = fields(tx_line) if tx_line else {}
    raw = fields(raw_line) if raw_line else {}
    result = fields(result_line) if result_line else {}

    checks += [
        ("blind_host_contract", host.get("identity_oracle_supplied") == "0" and host.get("binding_phrase_supplied") == "0"),
        ("blind_firmware_contract", boot.get("blind_identity") == "1" and boot.get("compiled_uid") == "0" and boot.get("compiled_seed") == "0"),
        ("profile_read_only", profile.get("pass") == "1" and profile.get("write_sent") == "0" and profile.get("writes_sent") == "0"),
        ("blind_sync", sync.get("pass") == "1" and int(sync.get("consistent_syncs", "0")) >= 2),
        ("blind_probe", probe.get("pass") == "1" and int(probe.get("positive_observations", "0")) >= 3),
        ("host_reconstruction", host_recon.get("pass") == "1" and host_recon.get("candidate_count") == "2" and host_recon.get("identity_oracle_used") == "0" and host_recon.get("tables_identical") == "1"),
        ("firmware_reconstruction", recon.get("pass") == "1" and recon.get("uid2_high_bit_ambiguous") == "1" and recon.get("tables_identical") == "1"),
        ("fhss_follow", follow.get("pass") == "1" and follow.get("table_positions") == "240" and int(follow.get("slots", "0")) in (480, 960) and int(follow.get("valid_packets", "0")) >= min(500, int(follow.get("slots", "0")))),
        ("fresh_sync", fresh.get("pass") == "1"),
        ("operator_off", off.get("pass") == "1"),
        ("operator_events", len(records(lines, "HOST_H44F_CORE_OPERATOR_EVENT,")) == 2),
        ("tx", tx.get("pass") == "1" and tx.get("operator_on_pass") == "1" and tx.get("tx_timeouts") == "0"),
        ("raw_capture", raw.get("pass") == "1" and raw.get("overflow") == "0"),
        ("firmware_result", result.get("verdict") == "PASS"),
        ("capture_complete", "H44F_CORE_CAPTURE_COMPLETE=YES" in lines and "H44F_CORE_CAPTURE_FAILURE=NONE" in lines),
        ("terminal_markers", "HELTEC_RF_TX_DISABLED" in lines and "GPIO47_INPUT" in lines and "GPIO42_INPUT" in lines and "Complete" in lines),
        ("no_bind_phrase_disclosure", not any("MY_BINDING_PHRASE" in line or "binding_phrase=" in line for line in lines)),
    ]

    required_result_flags = [
        "signatures_distinct", "profile_read_only_pass", "aeris_lock_pass",
        "baseline_pass", "blind_sync_pass", "probe_pass", "reconstruction_pass",
        "runtime_sync_pass", "fhss_follow_pass", "fresh_sync_pass",
        "operator_off_pass", "transition_pass", "tx_pass", "operator_on_pass",
        "takeover_pass", "incumbent_lock_pass", "aeris_recovery_pass",
        "raw_pass", "final_safe",
    ]
    checks.append(("all_result_flags", all(result.get(flag) == "1" for flag in required_result_flags)))

    failed = [name for name, passed in checks if not passed]
    for name, passed in checks:
        print(("PASS " if passed else "FAIL ") + name)
    print(f"H44F_CORE_OFFLINE_LOG_SHA256={hashlib.sha256(path.read_bytes()).hexdigest()}")
    print("H44F_CORE_OFFLINE_FAILED_CHECKS=" + (",".join(failed) if failed else "NONE"))
    print("H44F_CORE_OFFLINE_VERDICT=" + ("PASS" if not failed else "FAIL"))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())

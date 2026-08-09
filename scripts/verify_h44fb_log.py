#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import pathlib


def fields(line: str) -> dict[str, str]:
    return dict(part.split("=", 1) for part in line.split(",")[1:] if "=" in part)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("log")
    path = pathlib.Path(parser.parse_args().log)
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()

    def records(prefix: str) -> list[str]:
        return [line for line in lines if line.startswith(prefix)]

    tests = records("H44FB_PROFILE_TEST,")
    winners = [fields(line) for line in tests if fields(line).get("pass") == "1"]
    probe = records("H44FB_FIVE_HOP_PROBE,")
    blind_sync = records("H44FB_BLIND_SYNC,")
    purge = records("H44FB_PURGE,")
    observations = records("H44FB_PROBE_OBSERVATION,")
    host = records("HOST_H44FB_RECONSTRUCTION,")
    device = records("H44FB_RECONSTRUCTION,")
    follow = records("H44FB_FIVE_HOP_FOLLOW,")
    safe = records("H44FB_SAFE_STOP,")
    result = records("H44FB_RESULT,")
    guard = records("H44FB_RX_ONLY_GUARD,")
    stimulus = records("H44FB_AERIS_STIMULUS,")

    checks = [
        ("campaign_identity", len(records("H44FB_BOOT,")) == 1 and
         fields(records("H44FB_BOOT,")[0]).get("campaign") == "H44F-B"),
        ("six_profiles_unique_winner", len(tests) == 6 and len(winners) == 1),
        ("cold_profile_confirmation", len(records("H44FB_PROFILE_CONFIRM,")) == 1 and
         fields(records("H44FB_PROFILE_CONFIRM,")[0]).get("window_ms") == "6500" and
         fields(records("H44FB_PROFILE_CONFIRM,")[0]).get("valid_syncs") == "1" and
         fields(records("H44FB_PROFILE_CONFIRM,")[0]).get("pass") == "1"),
        ("throttle_minimum", len(stimulus) == 1 and
         fields(stimulus[0]).get("start_error") == "0" and
         fields(stimulus[0]).get("throttle_value") == "172" and
         fields(stimulus[0]).get("pass") == "1"),
        ("identity_purged", len(purge) == 1 and
         fields(purge[0]).get("pass") == "1" and
         fields(purge[0]).get("identity_handoff_bytes") == "0"),
        ("fresh_blind_sync", len(blind_sync) == 1 and len(purge) == 1 and
         fields(blind_sync[0]).get("max_timeout_us") == "6500000" and
         fields(blind_sync[0]).get("consistent_syncs") == "1" and
         fields(blind_sync[0]).get("crc_pass") == "1" and
         fields(blind_sync[0]).get("structure_pass") == "1" and
         fields(blind_sync[0]).get("pass") == "1" and
         lines.index(blind_sync[0]) > lines.index(purge[0])),
        ("exact_five_hop_probe", len(probe) == 1 and len(observations) == 5 and
         fields(probe[0]).get("distinct_hops") == "5" and
         fields(probe[0]).get("source_signature_matches") == "5" and
         fields(probe[0]).get("pass") == "1" and
         len({fields(line).get("fhss_index") for line in observations}) == 5),
        ("bounded_unique_bruteforce", len(host) == 1 and
         fields(host[0]).get("search_classes") == "32768" and
         fields(host[0]).get("candidate_count") == "1" and
         fields(host[0]).get("observations") == "5" and
         fields(host[0]).get("observation_model") in
             {"FIVE_EXACT", "FOUR_EXACT_ONE_ADJACENT"} and
         int(fields(host[0]).get("exact_matches", "0")) >= 4 and
         int(fields(host[0]).get("adjacent_matches", "9")) <= 1 and
         fields(host[0]).get("source_signature_matches") == "5" and
         fields(host[0]).get("pass") == "1"),
        ("firmware_reconstruction", len(device) == 1 and
         fields(device[0]).get("observation_model") == "EXACT_OR_ONE_ADJACENT" and
         int(fields(device[0]).get("exact_matches", "0")) >= 4 and
         int(fields(device[0]).get("adjacent_matches", "9")) <= 1 and
         fields(device[0]).get("pass") == "1" and
         fields(device[0]).get("binding_phrase_recovered") == "0"),
        ("five_hop_follow", len(follow) == 1 and
         fields(follow[0]).get("hops") == "5" and
         fields(follow[0]).get("crc_failures") == "0" and
         fields(follow[0]).get("channel_mismatches") == "0" and
         fields(follow[0]).get("pass") == "1"),
        ("rx_only", len(guard) == 1 and
         fields(guard[0]).get("heltec_rf_tx") == "0" and
         fields(guard[0]).get("op_set_tx_available") == "0" and
         not any("H44FB_TX," in line for line in lines)),
        ("safe_stop", len(safe) == 1 and fields(safe[0]).get("pass") == "1" and
         "HELTEC_RF_TX_DISABLED" in lines and "GPIO47_INPUT" in lines),
        ("global_result", len(result) == 1 and
         fields(result[0]).get("verdict") == "PASS" and
         fields(result[0]).get("final_safe") == "1"),
    ]
    failed = [name for name, passed in checks if not passed]
    for name, passed in checks:
        print(("PASS " if passed else "FAIL ") + name)
    print(f"H44FB_OFFLINE_LOG_SHA256={hashlib.sha256(path.read_bytes()).hexdigest()}")
    print("H44FB_OFFLINE_FAILED_CHECKS=" + (",".join(failed) if failed else "NONE"))
    print("H44FB_OFFLINE_VERDICT=" + ("PASS" if not failed else "FAIL"))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())

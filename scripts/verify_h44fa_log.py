#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import pathlib
import subprocess
import sys


def fields(line: str) -> dict[str, str]:
    return dict(part.split("=", 1) for part in line.split(",")[1:] if "=" in part)


def exact(lines: list[str], prefix: str) -> list[tuple[int, str]]:
    return [(i, line) for i, line in enumerate(lines) if line.startswith(prefix)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("log")
    args = ap.parse_args()
    path = pathlib.Path(args.log)
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    checks: list[tuple[str, bool]] = []
    tests = exact(lines, "H44F_PROFILE_TEST,")
    parsed = [fields(x[1]) for x in tests]
    winners = [p for p in parsed if p.get("pass") == "1"]
    checks.append(("six_profile_records", len(tests) == 6 and
                   {int(p.get("index", "-1")) for p in parsed} == set(range(6))))
    checks.append(("unique_profile_winner", len(winners) == 1))
    lock = exact(lines, "H44F_PROFILE_LOCK,")
    confirm = exact(lines, "H44F_PROFILE_CONFIRM,")
    handoff = exact(lines, "H44F_HANDOFF_TO_CORE,")
    guard = exact(lines, "H44F_RX_ONLY_GUARD,")
    result = exact(lines, "H44F_RESULT,")
    stimulus = exact(lines, "H44F_AERIS_STIMULUS,")
    stimulus_stop = exact(lines, "H44F_AERIS_STIMULUS_STOP,")
    lockf = fields(lock[0][1]) if len(lock) == 1 else {}
    confirmf = fields(confirm[0][1]) if len(confirm) == 1 else {}
    handofff = fields(handoff[0][1]) if len(handoff) == 1 else {}
    resultf = fields(result[0][1]) if len(result) == 1 else {}
    stimulusf = fields(stimulus[0][1]) if len(stimulus) == 1 else {}
    stimulus_stopf = fields(stimulus_stop[0][1]) if len(stimulus_stop) == 1 else {}
    checks.append(("aeris_stimulus_during_sweep", len(stimulus) == 1 and
                   stimulusf.get("started") == "1" and stimulusf.get("pass") == "1" and
                   stimulusf.get("gpio47") == "crsf_output" and
                   stimulusf.get("heltec_rf_tx") == "0" and
                   int(stimulusf.get("frames_sent", "0")) >=
                   int(stimulusf.get("minimum_frames", "1")) and tests and
                   stimulus[0][0] < tests[0][0]))
    checks.append(("profile_lock", len(lock) == 1 and lockf.get("pass") == "1" and
                   lockf.get("candidate_count") == "1" and winners and
                   lockf.get("name") == winners[0].get("name")))
    checks.append(("cold_confirmation", len(confirm) == 1 and
                   confirmf.get("pass") == "1" and confirmf.get("same_rate") == "1" and
                   confirmf.get("same_uid45") == "1" and lock and confirm[0][0] > lock[0][0]))
    purge_tokens = ["H44F_SWEEP_STATE_PURGED=YES", "H44F_IDENTITY_STATE_PURGED=YES",
                    "H44F_CLASSIFIER_STATE_PURGED=YES",
                    "H44F_RADIO_REINITIALIZED=YES", "H44F_BINDING_PHRASE_SUPPLIED=0",
                    "H44F_IDENTITY_ORACLE_SUPPLIED=0", "H44F_COMPILED_UID=0",
                    "H44F_COMPILED_SEED=0", "H44F_COMPILED_FHSS_TABLE=0"]
    checks.append(("state_and_identity_purged", all(token in lines for token in purge_tokens) and
                   "H44F_IDENTITY_HANDOFF_BYTES=0" in lines))
    checks.append(("sweep_rx_only", len(guard) == 1 and
                   fields(guard[0][1]).get("pass") == "1" and
                   fields(guard[0][1]).get("op_set_tx_calls") == "0" and
                   fields(guard[0][1]).get("heltec_rf_tx") == "0" and
                   fields(guard[0][1]).get("gpio47") == "crsf_stimulus"))
    checks.append(("aeris_stimulus_stopped_before_handoff",
                   len(stimulus_stop) == 1 and stimulus_stopf.get("pass") == "1" and
                   stimulus_stopf.get("stopped") == "1" and
                   stimulus_stopf.get("gpio47_input") == "1" and handoff and
                   stimulus_stop[0][0] < handoff[0][0]))
    blocked = handofff.get("reason") in {"OTA8_H44F_CORE_NOT_VALIDATED", "DVDA_H44F_CORE_NOT_VALIDATED"}
    checks.append(("handoff_standard_ota4_only", len(handoff) == 1 and
                   handofff.get("pass") == "1" and handofff.get("reason") == "NONE" and
                   not blocked and winners and winners[0].get("payload") == "8"))
    h43_sync = exact(lines, "H44F_CORE_BLIND_SYNC,")
    h43_tx = exact(lines, "H44F_CORE_TX,")
    checks.append(("fresh_h43_sync_after_purge", len(h43_sync) == 1 and handoff and
                   h43_sync[0][0] > handoff[0][0]))
    checks.append(("no_tx_during_sweep", not h43_tx or
                   (handoff and h43_tx[0][0] > handoff[0][0])))
    checks.append(("global_result", len(result) == 1 and
                   all(resultf.get(k) == "1" for k in
                       ("profile_sweep_pass", "profile_lock_pass", "profile_confirm_pass",
                        "handoff_pass", "core_final_pass", "final_safe")) and
                   resultf.get("verdict") == "PASS"))

    h43_verifier = pathlib.Path(__file__).with_name("verify_h44f_core_log.py")
    h43 = subprocess.run([sys.executable, str(h43_verifier), str(path)],
                         text=True, capture_output=True, check=False)
    print(h43.stdout, end="")
    checks.append(("complete_h43_verdict", h43.returncode == 0 and
                   "H44F_CORE_OFFLINE_VERDICT=PASS" in h43.stdout))
    failed = [name for name, passed in checks if not passed]
    for name, passed in checks:
        print(("PASS " if passed else "FAIL ") + name)
    print(f"H44F_OFFLINE_LOG_SHA256={hashlib.sha256(path.read_bytes()).hexdigest()}")
    print("H44F_OFFLINE_FAILED_CHECKS=" + (",".join(failed) if failed else "NONE"))
    print("H44F_OFFLINE_VERDICT=" + ("PASS" if not failed else "FAIL"))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())

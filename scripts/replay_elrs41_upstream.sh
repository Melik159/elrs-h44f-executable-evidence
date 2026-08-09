#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 /path/to/ExpressLRS-4.1.0" >&2
  exit 2
fi

source_root="$(realpath "$1")"
script_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONDONTWRITEBYTECODE=1
expected_commit="a9d4a9cb5b5687c4c9d7e9e7fbdf44ad93651da6"
expected_matrix="a82024c1f89fcde103406c633fa8495b0bd6cea50c5762ef5cd51d8eb02ff303"
expected_bytes=7864320

actual_commit="$(git -C "$source_root" rev-parse HEAD)"
if [[ "$actual_commit" != "$expected_commit" ]]; then
  echo "ELRS41_REPLAY_ERROR=wrong_commit:$actual_commit" >&2
  exit 1
fi
if [[ -n "$(git -C "$source_root" status --porcelain --untracked-files=no)" ]]; then
  echo "ELRS41_REPLAY_ERROR=tracked_worktree_not_clean" >&2
  exit 1
fi

declare -A expected_sources=(
  [src/lib/FHSS/FHSS.cpp]=1e0fed88b3b699ac1274e4debf42809f88af74856cdebc7d2249b63a96d2063d
  [src/lib/FHSS/FHSS.h]=98b55ec38194a6722876d62134a5e6a160475e8b81366d592abbf67f193c41b8
  [src/lib/FHSS/random.cpp]=b1eda6ed1f146dc85e8568de31e6e0dae9f4970e165b2bb9ddfd2d315eaec871
  [src/lib/FHSS/random.h]=9c05dcd7763730843ff4edbeddbcf0e18a5999559be9ca37630b7d14283bc03f
)
for relative in "${!expected_sources[@]}"; do
  actual="$(sha256sum "$source_root/$relative" | awk '{print $1}')"
  if [[ "$actual" != "${expected_sources[$relative]}" ]]; then
    echo "ELRS41_REPLAY_ERROR=source_hash:$relative" >&2
    exit 1
  fi
done

temporary="$(mktemp -d)"
trap 'rm -rf -- "$temporary"' EXIT

g++ -std=c++17 -O2 -Wall -Wextra -Wno-unused-parameter \
  -DUNIT_TEST=1 -DTARGET_NATIVE -DRADIO_SX127X \
  -I"$script_root/elrs41_reference/host_stubs" \
  -I"$source_root/src/include" \
  -I"$source_root/src/lib/FHSS" \
  "$script_root/elrs41_reference/direct_fhss_driver.cpp" \
  "$source_root/src/lib/FHSS/FHSS.cpp" \
  "$source_root/src/lib/FHSS/random.cpp" \
  -o "$temporary/upstream_fhss"

"$temporary/upstream_fhss" 0x56 0x78 "$temporary/upstream.bin"
python3 "$script_root/generate_elrs41_matrix.py" "$temporary/python.bin"

upstream_bytes="$(stat -c %s "$temporary/upstream.bin")"
python_bytes="$(stat -c %s "$temporary/python.bin")"
upstream_hash="$(sha256sum "$temporary/upstream.bin" | awk '{print $1}')"
python_hash="$(sha256sum "$temporary/python.bin" | awk '{print $1}')"

[[ "$upstream_bytes" == "$expected_bytes" ]]
[[ "$python_bytes" == "$expected_bytes" ]]
[[ "$upstream_hash" == "$expected_matrix" ]]
[[ "$python_hash" == "$expected_matrix" ]]
cmp --silent "$temporary/upstream.bin" "$temporary/python.bin"

echo "ELRS41_REPLAY_COMMIT=$actual_commit"
echo "ELRS41_REPLAY_CLASSES=32768"
echo "ELRS41_REPLAY_POSITIONS_PER_CLASS=240"
echo "ELRS41_REPLAY_COMPARISONS=$expected_bytes"
echo "ELRS41_REPLAY_MISMATCHES=0"
echo "ELRS41_REPLAY_MATRIX_SHA256=$upstream_hash"
echo "ELRS41_UPSTREAM_REPLAY_VERDICT=PASS"

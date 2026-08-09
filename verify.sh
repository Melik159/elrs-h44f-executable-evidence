#!/usr/bin/env bash
set -euo pipefail

proof_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
export PYTHONDONTWRITEBYTECODE=1
exec python3 "$proof_dir/verify.py" "$@"

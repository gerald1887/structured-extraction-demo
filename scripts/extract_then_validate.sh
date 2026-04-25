#!/usr/bin/env bash
# Run `extract run` with the same arguments, then validate the output JSON with
# scripts/validate_artifact_sentinel.py which invokes Sentinel CLI (no second provider call).
# Requires --output and --schema in the argument list (single run mode).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VALIDATOR="${REPO_ROOT}/scripts/validate_artifact_sentinel.py"

if [[ ! -f "$VALIDATOR" ]]; then
  echo "extract_then_validate: missing ${VALIDATOR}" >&2
  exit 2
fi

if ! command -v extract &>/dev/null; then
  echo "extract_then_validate: 'extract' not on PATH (install package: pip install -e .)" >&2
  exit 2
fi

# Invoked as: .../extract_then_validate.sh run --input ... (first arg is the extract subcommand)
extract "$@" || exit "$?"

# Parse --output and --schema from the same args extract received.
output_path=""
schema_path=""
args=("$@")
i=0
n=${#args[@]}
while [[ $i -lt $n ]]; do
  a="${args[i]}"
  if [[ "$a" == "--output" ]]; then
    if [[ $((i + 1)) -ge $n ]]; then
      echo "extract_then_validate: --output requires a value" >&2
      exit 2
    fi
    i=$((i + 1))
    output_path="${args[i]}"
  elif [[ "$a" == "--schema" ]]; then
    if [[ $((i + 1)) -ge $n ]]; then
      echo "extract_then_validate: --schema requires a value" >&2
      exit 2
    fi
    i=$((i + 1))
    schema_path="${args[i]}"
  fi
  i=$((i + 1))
done

if [[ -z "$output_path" || -z "$schema_path" ]]; then
  echo "extract_then_validate: need both --output and --schema in arguments for validation" >&2
  exit 2
fi

exec python3 "$VALIDATOR" --input "$output_path" --schema "$schema_path"

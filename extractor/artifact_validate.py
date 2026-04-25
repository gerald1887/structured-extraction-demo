from __future__ import annotations

import subprocess
import sys


def _print(msg: str) -> None:
    print(msg, file=sys.stdout, flush=True)


def validate_artifact_with_sentinel(input_path: str, schema_path: str, sentinel_bin: str) -> int:
    cmd = [sentinel_bin, "validate", "--input", input_path, "--schema", schema_path]
    try:
        proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
    except FileNotFoundError:
        _print("ERROR: Execution failed")
        _print(f"SENTINEL_CLI_NOT_FOUND: '{sentinel_bin}' is not on PATH")
        return 2
    except OSError as exc:
        _print("ERROR: Execution failed")
        _print(f"SENTINEL_CLI_EXEC_ERROR: {exc!s}")
        return 2

    combined = ((proc.stdout or "") + (proc.stderr or "")).strip()
    if proc.returncode == 0:
        _print("PASS: Contract satisfied")
        if combined:
            _print(combined)
        return 0
    if proc.returncode == 1:
        _print("FAIL: Contract violated")
        if combined:
            _print(combined)
        return 1

    _print("ERROR: Execution failed")
    if combined:
        _print(combined)
    else:
        _print(f"SENTINEL_CLI_EXIT_NONSTANDARD: exit={proc.returncode}")
    return 2

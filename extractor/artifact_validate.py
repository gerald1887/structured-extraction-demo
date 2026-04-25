from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _print(msg: str) -> None:
    print(msg, file=sys.stdout, flush=True)


def _write_failure_output(path: str, sentinel_exit_code: int, stdout: str, stderr: str) -> None:
    payload = {
        "status": "FAIL",
        "sentinel_exit_code": sentinel_exit_code,
        "stdout": stdout,
        "stderr": stderr,
    }
    Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_success_output(path: str, exit_code: int, stdout: str, stderr: str) -> None:
    payload = {
        "exit_code": exit_code,
        "stderr": stderr,
        "stdout": stdout,
    }
    Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def validate_artifact_with_sentinel(
    input_path: str,
    schema_path: str,
    sentinel_bin: str,
    failure_output_path: str | None = None,
    success_output_path: str | None = None,
) -> int:
    cmd = [sentinel_bin, "validate", "--input", input_path, "--schema", schema_path]
    try:
        proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
    except FileNotFoundError:
        if failure_output_path is not None:
            try:
                _write_failure_output(
                    path=failure_output_path,
                    sentinel_exit_code=2,
                    stdout="",
                    stderr="",
                )
            except OSError:
                pass
        _print("ERROR: Execution failed")
        _print(f"SENTINEL_CLI_NOT_FOUND: '{sentinel_bin}' is not on PATH")
        return 2
    except OSError as exc:
        if failure_output_path is not None:
            try:
                _write_failure_output(
                    path=failure_output_path,
                    sentinel_exit_code=2,
                    stdout="",
                    stderr="",
                )
            except OSError:
                pass
        _print("ERROR: Execution failed")
        _print(f"SENTINEL_CLI_EXEC_ERROR: {exc!s}")
        return 2

    stdout = proc.stdout or ""
    stderr = proc.stderr or ""
    combined = (stdout + stderr).strip()
    if proc.returncode == 0:
        if success_output_path is not None:
            try:
                _write_success_output(
                    path=success_output_path,
                    exit_code=proc.returncode,
                    stdout=stdout,
                    stderr=stderr,
                )
            except OSError:
                pass
        _print("PASS: Contract satisfied")
        if combined:
            _print(combined)
        return 0
    if failure_output_path is not None:
        try:
            _write_failure_output(
                path=failure_output_path,
                sentinel_exit_code=proc.returncode,
                stdout=stdout,
                stderr=stderr,
            )
        except OSError:
            pass
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

#!/usr/bin/env python3
"""Validate a JSON artifact by invoking Sentinel CLI as a subprocess.

No Sentinel Python imports are used. Exit code mapping is deterministic:
0 = PASS, 1 = contract validation failure, 2 = execution/setup/internal failure.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate a JSON file against a schema by invoking Sentinel CLI.",
    )
    parser.add_argument(
        "--input",
        required=True,
        metavar="PATH",
        help="Path to the JSON artifact to validate (e.g. extract output).",
    )
    parser.add_argument(
        "--schema",
        required=True,
        metavar="PATH",
        help="Path to the JSON Schema file.",
    )
    parser.add_argument(
        "--sentinel-bin",
        default=os.environ.get("SENTINEL_BIN", "sentinel"),
        metavar="CMD",
        help="Sentinel CLI binary path (default: sentinel, or SENTINEL_BIN env var).",
    )
    args = parser.parse_args(argv)

    in_path = Path(args.input)
    if not in_path.is_file():
        print("ERROR: Execution failed", file=sys.stdout, flush=True)
        if not in_path.exists():
            print(
                f"FILE_NOT_FOUND: artifact file not found at {in_path}",
                file=sys.stdout,
                flush=True,
            )
        else:
            print(
                f"FILE_READ_ERROR: artifact path is not a regular file at {in_path}",
                file=sys.stdout,
                flush=True,
            )
        return 2

    try:
        raw = in_path.read_text(encoding="utf-8")
    except OSError as exc:
        print("ERROR: Execution failed", file=sys.stdout, flush=True)
        print(
            f"FILE_READ_ERROR: {exc!s}",
            file=sys.stdout,
            flush=True,
        )
        return 2

    try:
        json.loads(raw)
    except (json.JSONDecodeError, ValueError) as exc:
        print("ERROR: Execution failed", file=sys.stdout, flush=True)
        print(
            f"JSON_PARSE_ERROR: artifact is not valid JSON ({exc!s})",
            file=sys.stdout,
            flush=True,
        )
        return 2

    schema_path = Path(args.schema)
    if not schema_path.is_file():
        print("ERROR: Execution failed", file=sys.stdout, flush=True)
        if not schema_path.exists():
            print(
                f"FILE_NOT_FOUND: schema file not found at {schema_path}",
                file=sys.stdout,
                flush=True,
            )
        else:
            print(
                f"FILE_READ_ERROR: schema path is not a regular file at {schema_path}",
                file=sys.stdout,
                flush=True,
            )
        return 2

    cmd = [
        args.sentinel_bin,
        "validate",
        "--input",
        str(in_path),
        "--schema",
        str(schema_path),
    ]
    try:
        proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
    except FileNotFoundError:
        print("ERROR: Execution failed", file=sys.stdout, flush=True)
        print(
            f"SENTINEL_CLI_NOT_FOUND: '{args.sentinel_bin}' is not on PATH",
            file=sys.stdout,
            flush=True,
        )
        return 2
    except OSError as exc:
        print("ERROR: Execution failed", file=sys.stdout, flush=True)
        print(
            f"SENTINEL_CLI_EXEC_ERROR: {exc!s}",
            file=sys.stdout,
            flush=True,
        )
        return 2

    combined = ((proc.stdout or "") + (proc.stderr or "")).strip()
    if proc.returncode == 0:
        print("PASS: Contract satisfied", file=sys.stdout, flush=True)
        if combined:
            print(combined, file=sys.stdout, flush=True)
        return 0
    if proc.returncode == 1:
        print("FAIL: Contract violated", file=sys.stdout, flush=True)
        if combined:
            print(combined, file=sys.stdout, flush=True)
        return 1

    print("ERROR: Execution failed", file=sys.stdout, flush=True)
    if combined:
        print(combined, file=sys.stdout, flush=True)
    else:
        print(
            f"SENTINEL_CLI_EXIT_NONSTANDARD: exit={proc.returncode}",
            file=sys.stdout,
            flush=True,
        )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

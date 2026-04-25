#!/usr/bin/env python3
"""Validate a JSON artifact on disk with Sentinel’s schema stack (no provider, no `sentinel run`).

Validation logic imports only: load_schema, validate_schema_structure, validate_instance.
Exit: 0 PASS, 1 schema validation FAIL, 2 ERROR.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sentinel.core.errors import SentinelError
from sentinel.core.files import load_schema
from sentinel.core.schema import validate_instance, validate_schema_structure


def _line(err: SentinelError) -> str:
    """One deterministic, CI-readable line; mirrors sentinel.core.errors.render_error style."""
    parts: list[str] = [f"{err.category} [{err.code}]"]
    if err.location is not None:
        parts.append(f"location={err.location}")
    parts.append(f"message={err.message}")
    if err.details:
        inner = ", ".join(f"{k}={err.details[k]}" for k in sorted(err.details))
        parts.append(f"details={{{inner}}}")
    return " ".join(parts)


def _print_error_status(lead: str) -> None:
    print(lead, file=sys.stdout, flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate a JSON file against a JSON schema using Sentinel schema validation.",
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
        help="Path to the JSON Schema file (Draft 2020-12 as used by Sentinel).",
    )
    args = parser.parse_args(argv)

    in_path = Path(args.input)
    if not in_path.is_file():
        _print_error_status("ERROR: Execution failed")
        if not in_path.exists():
            print(
                "FILE_NOT_FOUND [SENTINEL_FILE_NOT_FOUND] message=File not found. location="
                f"{in_path}",
                file=sys.stdout,
                flush=True,
            )
        else:
            print(
                "FILE_READ_ERROR [SENTINEL_FILE_READ_ERROR] message=Path is not a regular file. "
                f"location={in_path}",
                file=sys.stdout,
                flush=True,
            )
        return 2

    try:
        raw = in_path.read_text(encoding="utf-8")
    except OSError as exc:
        _print_error_status("ERROR: Execution failed")
        print(
            f"FILE_READ_ERROR [SENTINEL_FILE_READ_ERROR] message={exc!s} location={in_path}",
            file=sys.stdout,
            flush=True,
        )
        return 2

    try:
        instance: object = json.loads(raw)
    except (json.JSONDecodeError, ValueError) as exc:
        _print_error_status("ERROR: Execution failed")
        print(
            f"JSON_PARSE_ERROR [SENTINEL_JSON_PARSE_ERROR] message=Artifact is not valid JSON. "
            f"details=error={str(exc)!r}",
            file=sys.stdout,
            flush=True,
        )
        return 2

    schema = load_schema(args.schema)
    if isinstance(schema, SentinelError):
        _print_error_status("ERROR: Execution failed")
        print(_line(schema), file=sys.stdout, flush=True)
        return 2

    if not isinstance(schema, (dict, list)):
        _print_error_status("ERROR: Execution failed")
        print(
            "INTERNAL_ERROR [SENTINEL_UNEXPECTED_SCHEMA_TYPE] message=Schema top-level value must be object or array.",
            file=sys.stdout,
            flush=True,
        )
        return 2

    struct_err = validate_schema_structure(schema)
    if struct_err is not None:
        _print_error_status("ERROR: Execution failed")
        print(_line(struct_err), file=sys.stdout, flush=True)
        return 2

    val_err = validate_instance(instance, schema)
    if val_err is not None:
        print("FAIL: Contract violated", file=sys.stdout, flush=True)
        print(_line(val_err), file=sys.stdout, flush=True)
        return 1

    print("PASS: Contract satisfied", file=sys.stdout, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

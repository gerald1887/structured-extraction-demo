#!/usr/bin/env python3
"""Validate a JSON artifact by invoking Sentinel CLI as a subprocess.

No Sentinel Python imports are used. Exit code mapping is deterministic:
0 = PASS, 1 = contract validation failure, 2 = execution/setup/internal failure.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from extractor.artifact_validate import validate_artifact_with_sentinel

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

    return validate_artifact_with_sentinel(
        input_path=args.input,
        schema_path=args.schema,
        sentinel_bin=args.sentinel_bin,
    )


if __name__ == "__main__":
    raise SystemExit(main())

import json
from pathlib import Path

from extractor.errors import AppError, FILE_ERROR


def _canonical_json_text(data: dict) -> str:
    return json.dumps(data, indent=2, sort_keys=True) + "\n"


def _write_canonical_json(path: str, data: dict) -> None:
    try:
        Path(path).write_text(_canonical_json_text(data), encoding="utf-8")
    except Exception as exc:
        raise AppError(FILE_ERROR, f"Failed to write file: {path}") from exc


def write_output_json(path: str, data: dict) -> None:
    _write_canonical_json(path, data)


def write_metadata_json(path: str, data: dict) -> None:
    _write_canonical_json(path, data)


def write_error_json(path: str, data: dict) -> None:
    _write_canonical_json(path, data)


def write_report_json(path: str, data: dict) -> None:
    _write_canonical_json(path, data)


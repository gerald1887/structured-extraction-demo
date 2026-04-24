import json
from pathlib import Path

from extractor.errors import AppError, FILE_ERROR, INTERNAL_ERROR


def write_snapshot(path: str, data: object) -> None:
    try:
        Path(path).write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except Exception as exc:
        raise AppError(FILE_ERROR, f"Failed to write file: {path}") from exc


def load_snapshot(path: str) -> object:
    try:
        raw = Path(path).read_text(encoding="utf-8")
    except Exception as exc:
        raise AppError(FILE_ERROR, f"Failed to read file: {path}") from exc
    try:
        return json.loads(raw)
    except Exception as exc:
        raise AppError(INTERNAL_ERROR, "Internal error") from exc


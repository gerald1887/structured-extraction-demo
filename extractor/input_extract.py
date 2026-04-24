import json
from pathlib import Path

from extractor.errors import AppError, FILE_ERROR
from extractor.preprocess import preprocess_text


def _collect_json_strings(value: object, out: list[str]) -> None:
    if isinstance(value, str):
        out.append(value)
        return
    if isinstance(value, list):
        for item in value:
            _collect_json_strings(item, out)
        return
    if isinstance(value, dict):
        for nested in value.values():
            _collect_json_strings(nested, out)


def extract_input_text(path: str) -> str:
    input_path = Path(path)
    suffix = input_path.suffix
    try:
        raw = input_path.read_text(encoding="utf-8")
    except Exception as exc:
        raise AppError(FILE_ERROR, f"Failed to read file: {path}") from exc

    if suffix in {".txt", ".md"}:
        return preprocess_text(raw)
    if suffix == ".json":
        try:
            data = json.loads(raw)
        except Exception as exc:
            raise AppError(FILE_ERROR, f"Failed to read file: {path}") from exc
        strings: list[str] = []
        _collect_json_strings(data, strings)
        return preprocess_text("\n".join(strings))

    raise AppError(FILE_ERROR, f"Failed to read file: {path}")


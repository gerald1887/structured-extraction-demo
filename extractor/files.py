from importlib.resources import files
from pathlib import Path

from extractor.errors import AppError, FILE_ERROR, INTERNAL_ERROR
from extractor.input_extract import extract_input_text


def read_text_file(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8")
    except Exception as exc:
        raise AppError(FILE_ERROR, f"Failed to read file: {path}") from exc


def read_input_text(path: str) -> str:
    return extract_input_text(path)


def read_prompt_template() -> str:
    try:
        return files("extractor").joinpath("prompts/extraction_prompt.txt").read_text(encoding="utf-8")
    except Exception as exc:
        raise AppError(FILE_ERROR, "Failed to read file: extraction_prompt.txt") from exc


def read_schema_file(path: str) -> dict:
    import json

    raw = read_text_file(path)
    try:
        return json.loads(raw)
    except Exception as exc:
        raise AppError(INTERNAL_ERROR, "Internal error") from exc


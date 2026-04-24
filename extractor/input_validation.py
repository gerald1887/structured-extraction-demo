from pathlib import Path

from extractor.errors import AppError, FILE_ERROR

MAX_INPUT_BYTES = 100_000


def validate_input_file(path: str) -> None:
    try:
        raw = Path(path).read_bytes()
    except Exception as exc:
        raise AppError(FILE_ERROR, f"Failed to read file: {path}") from exc

    if len(raw) > MAX_INPUT_BYTES:
        raise AppError(FILE_ERROR, f"Input exceeds max size limit: {MAX_INPUT_BYTES} bytes")

    try:
        raw.decode("utf-8")
    except Exception as exc:
        raise AppError(FILE_ERROR, "Input is not valid UTF-8") from exc

    if len(raw) == 0:
        raise AppError(FILE_ERROR, "Input is empty")

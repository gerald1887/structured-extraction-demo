import json

from extractor.errors import AppError, JSON_PARSE_ERROR


def parse_json_strict(raw_text: str) -> dict:
    stripped = raw_text.strip()
    if not (stripped.startswith("{") and stripped.endswith("}")):
        raise AppError(JSON_PARSE_ERROR, "Invalid JSON returned by model")

    try:
        data = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise AppError(JSON_PARSE_ERROR, "Invalid JSON returned by model") from exc

    if not isinstance(data, dict):
        raise AppError(JSON_PARSE_ERROR, "Invalid JSON returned by model")

    return data


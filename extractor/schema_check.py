from dataclasses import dataclass
import json
from pathlib import Path

from extractor.errors import AppError, FILE_ERROR, INTERNAL_ERROR, JSON_PARSE_ERROR, SCHEMA_VALIDATION_ERROR
from extractor.files import read_schema_file, read_text_file
from extractor.schema import validate_against_schema


@dataclass
class SchemaCheckItem:
    path: str
    classification: str


@dataclass
class SchemaCheckResult:
    items: list[SchemaCheckItem]
    total: int
    compatible: int
    breaking_change: int


def _collect_artifact_paths(input_path: str) -> list[Path]:
    path = Path(input_path)
    if path.is_file():
        return [path]
    if path.is_dir():
        return sorted((p for p in path.iterdir() if p.is_file() and p.suffix == ".json"), key=lambda p: p.name)
    raise AppError(FILE_ERROR, f"Failed to read file: {input_path}")


def _load_json_artifact(path: Path):
    raw = read_text_file(str(path))
    try:
        return json.loads(raw)
    except Exception as exc:
        raise AppError(JSON_PARSE_ERROR, "Invalid JSON returned by model") from exc


def run_schema_check(input_path: str, new_schema_path: str) -> SchemaCheckResult:
    artifact_paths = _collect_artifact_paths(input_path)
    schema = read_schema_file(new_schema_path)
    items: list[SchemaCheckItem] = []
    compatible = 0
    breaking_change = 0

    for artifact_path in artifact_paths:
        value = _load_json_artifact(artifact_path)
        candidate = value
        if isinstance(value, dict):
            candidate = {k: v for k, v in value.items() if k != "_meta"}
        try:
            validate_against_schema(candidate, schema)
            classification = "COMPATIBLE"
            compatible += 1
        except AppError as err:
            if err.error_type != SCHEMA_VALIDATION_ERROR:
                raise
            classification = "BREAKING_CHANGE"
            breaking_change += 1
        except Exception as exc:
            raise AppError(INTERNAL_ERROR, "Internal error") from exc
        items.append(SchemaCheckItem(path=artifact_path.name, classification=classification))

    return SchemaCheckResult(
        items=items,
        total=len(items),
        compatible=compatible,
        breaking_change=breaking_change,
    )


def write_schema_check_report(path: str, result: SchemaCheckResult) -> None:
    payload = {
        "items": [{"path": item.path, "classification": item.classification} for item in result.items],
        "summary": {
            "total": result.total,
            "compatible": result.compatible,
            "breaking_change": result.breaking_change,
        },
    }
    try:
        Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except Exception as exc:
        raise AppError(FILE_ERROR, f"Failed to write file: {path}") from exc

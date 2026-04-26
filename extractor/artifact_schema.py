from __future__ import annotations

from extractor.errors import AppError, SCHEMA_VALIDATION_ERROR


def validate_artifact_object(data: object) -> dict:
    if not isinstance(data, dict):
        raise AppError(SCHEMA_VALIDATION_ERROR, "Artifact must be a JSON object")
    required = {"status", "exit_code", "stdout", "stderr"}
    if set(data.keys()) != required:
        raise AppError(SCHEMA_VALIDATION_ERROR, "Artifact has invalid fields")
    if data.get("status") not in {"PASS", "FAIL", "ERROR"}:
        raise AppError(SCHEMA_VALIDATION_ERROR, "Artifact has invalid status")
    exit_code = data.get("exit_code")
    if isinstance(exit_code, bool) or not isinstance(exit_code, int):
        raise AppError(SCHEMA_VALIDATION_ERROR, "Artifact exit_code must be int")
    if exit_code < 0 or exit_code > 255:
        raise AppError(SCHEMA_VALIDATION_ERROR, "Artifact exit_code must be in range 0-255")
    if not isinstance(data.get("stdout"), str):
        raise AppError(SCHEMA_VALIDATION_ERROR, "Artifact stdout must be string")
    if not isinstance(data.get("stderr"), str):
        raise AppError(SCHEMA_VALIDATION_ERROR, "Artifact stderr must be string")
    return data


def validate_artifact(artifact: object) -> dict:
    return validate_artifact_object(artifact)

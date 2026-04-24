from jsonschema import ValidationError, validate

from extractor.errors import AppError, SCHEMA_VALIDATION_ERROR


def validate_against_schema(data: dict, schema: dict) -> None:
    try:
        validate(instance=data, schema=schema)
    except ValidationError as exc:
        if exc.validator == "required" and isinstance(exc.validator_value, list) and isinstance(exc.instance, dict):
            missing_fields = [field for field in exc.validator_value if field not in exc.instance]
            if missing_fields:
                raise AppError(SCHEMA_VALIDATION_ERROR, f"Missing required field: {missing_fields[0]}") from exc
        raise AppError(SCHEMA_VALIDATION_ERROR, "Schema validation failed") from exc


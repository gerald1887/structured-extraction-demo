from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path

from extractor.errors import (
    AppError,
    EMPTY_OUTPUT_ERROR,
    FILE_ERROR,
    INTERNAL_ERROR,
    JSON_PARSE_ERROR,
    SCHEMA_VALIDATION_ERROR,
)
from extractor.files import read_input_text, read_prompt_template, read_schema_file, read_text_file
from extractor.hash_utils import compute_sha256, compute_sha256_bytes
from extractor.input_validation import validate_input_file
from extractor.json_parse import parse_json_strict
from extractor.output import write_metadata_json, write_output_json
from extractor.prompt_builder import build_prompt
from extractor.provider.base import Provider
from extractor.redaction import apply_redaction, load_redaction_config
from extractor.schema import validate_against_schema


@dataclass
class RunResult:
    success: bool
    error: AppError | None = None
    data: dict | None = None
    prompt_hash: str | None = None


@dataclass
class BatchRunResult:
    total: int
    success: int
    contract_failure: int
    execution_error: int


def _is_semantically_empty(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value == ""
    if isinstance(value, list):
        return len(value) == 0 or all(_is_semantically_empty(item) for item in value)
    if isinstance(value, dict):
        return len(value) == 0 or all(_is_semantically_empty(v) for v in value.values())
    return False


def _compute_file_sha256(path: str) -> str:
    try:
        return compute_sha256_bytes(Path(path).read_bytes())
    except Exception as exc:
        raise AppError(FILE_ERROR, f"Failed to read file: {path}") from exc


def run_extraction(
    input_path: str,
    schema_path: str,
    output_path: str,
    model: str,
    provider: Provider,
    temperature: float = 0.0,
    max_tokens: int | None = None,
    fail_on_empty: bool = False,
    capture_output_path: str | None = None,
    replay_output_path: str | None = None,
    redaction_config_path: str | None = None,
    expected_prompt_hash: str | None = None,
    write_metadata: bool = True,
) -> RunResult:
    prompt_hash: str | None = None
    try:
        validate_input_file(input_path)
        input_text = read_input_text(input_path)
        prompt_template = read_prompt_template()
        schema = read_schema_file(schema_path)

        schema_text = json.dumps(schema, sort_keys=True)
        prompt = build_prompt(template=prompt_template, schema_text=schema_text, input_text=input_text)
        prompt_hash = compute_sha256(prompt)
        if expected_prompt_hash is not None and prompt_hash != expected_prompt_hash:
            return RunResult(
                success=False,
                error=AppError(INTERNAL_ERROR, "Prompt hash mismatch"),
                prompt_hash=prompt_hash,
            )
        if replay_output_path is not None:
            raw_response = read_text_file(replay_output_path)
        else:
            raw_response = provider.generate(prompt=prompt, model=model, temperature=temperature, max_tokens=max_tokens)
            if capture_output_path is not None:
                try:
                    Path(capture_output_path).write_text(raw_response, encoding="utf-8")
                except Exception as exc:
                    raise AppError(FILE_ERROR, f"Failed to write file: {capture_output_path}") from exc

        parsed = parse_json_strict(raw_response)
        validate_against_schema(parsed, schema)
        redaction_applied = redaction_config_path is not None
        payload = dict(parsed)
        if redaction_config_path is not None:
            redaction_config = load_redaction_config(redaction_config_path)
            payload = apply_redaction(payload, redaction_config)
        if fail_on_empty:
            candidate = {k: v for k, v in payload.items() if k != "_meta"}
            if _is_semantically_empty(candidate):
                return RunResult(
                    success=False,
                    error=AppError(EMPTY_OUTPUT_ERROR, "Semantically empty output"),
                    prompt_hash=prompt_hash,
                )
        write_output_json(output_path, payload)
        if write_metadata:
            metadata = {
                "input_hash": _compute_file_sha256(input_path),
                "schema_hash": _compute_file_sha256(schema_path),
                "provider": provider.name,
                "model": model,
                "input_file": Path(input_path).name,
                "temperature": temperature,
                "prompt_hash": prompt_hash,
                "redaction_applied": redaction_applied,
                "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
            write_metadata_json(f"{output_path}.meta.json", metadata)
        return RunResult(success=True, data=payload, prompt_hash=prompt_hash)
    except AppError as err:
        return RunResult(success=False, error=err, prompt_hash=prompt_hash)
    except Exception:
        return RunResult(success=False, error=AppError(INTERNAL_ERROR, "Internal error"), prompt_hash=prompt_hash)


def run_extraction_data(
    input_path: str,
    schema_path: str,
    model: str,
    provider: Provider,
    temperature: float = 0.0,
    max_tokens: int | None = None,
) -> RunResult:
    try:
        validate_input_file(input_path)
        input_text = read_input_text(input_path)
        prompt_template = read_prompt_template()
        schema = read_schema_file(schema_path)

        schema_text = json.dumps(schema, sort_keys=True)
        prompt = build_prompt(template=prompt_template, schema_text=schema_text, input_text=input_text)
        raw_response = provider.generate(prompt=prompt, model=model, temperature=temperature, max_tokens=max_tokens)

        parsed = parse_json_strict(raw_response)
        validate_against_schema(parsed, schema)
        return RunResult(success=True, data=parsed)
    except AppError as err:
        return RunResult(success=False, error=err)
    except Exception:
        return RunResult(success=False, error=AppError(INTERNAL_ERROR, "Internal error"))


def run_batch_extraction(
    input_dir: str,
    schema_path: str,
    output_dir: str,
    model: str,
    provider: Provider,
    temperature: float = 0.0,
    max_tokens: int | None = None,
    fail_on_empty: bool = False,
    capture_output_path: str | None = None,
    replay_output_path: str | None = None,
    redaction_config_path: str | None = None,
) -> BatchRunResult:
    input_dir_path = Path(input_dir)
    output_dir_path = Path(output_dir)
    try:
        if not input_dir_path.exists() or not input_dir_path.is_dir():
            raise AppError(FILE_ERROR, f"Failed to read file: {input_dir}")
        output_dir_path.mkdir(parents=True, exist_ok=True)
        supported_paths: list[Path] = []
        for ext in (".txt", ".md", ".json"):
            supported_paths.extend(input_dir_path.glob(f"*{ext}"))
        input_paths = sorted(supported_paths, key=lambda p: p.name)
        stems = [p.stem for p in input_paths]
        seen: set[str] = set()
        duplicate_stems: list[str] = []
        for stem in stems:
            if stem in seen and stem not in duplicate_stems:
                duplicate_stems.append(stem)
            seen.add(stem)
        if duplicate_stems:
            raise AppError(FILE_ERROR, f"Failed to read file: duplicate stems: {','.join(duplicate_stems)}")
    except AppError:
        raise
    except Exception as exc:
        raise AppError(FILE_ERROR, f"Failed to write file: {output_dir}") from exc

    total = len(input_paths)
    success = 0
    contract_failure = 0
    execution_error = 0

    for input_path in input_paths:
        output_path = output_dir_path / f"{input_path.stem}.json"
        result = run_extraction(
            input_path=str(input_path),
            schema_path=schema_path,
            output_path=str(output_path),
            model=model,
            provider=provider,
            temperature=temperature,
            max_tokens=max_tokens,
            fail_on_empty=fail_on_empty,
            capture_output_path=capture_output_path,
            replay_output_path=replay_output_path,
            redaction_config_path=redaction_config_path,
            write_metadata=False,
        )
        if result.success:
            success += 1
            continue

        if result.error and result.error.error_type in {JSON_PARSE_ERROR, SCHEMA_VALIDATION_ERROR, EMPTY_OUTPUT_ERROR}:
            contract_failure += 1
        else:
            execution_error += 1

    return BatchRunResult(
        total=total,
        success=success,
        contract_failure=contract_failure,
        execution_error=execution_error,
    )


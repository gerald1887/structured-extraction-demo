import argparse
import json
from pathlib import Path
import sys

from extractor.errors import (
    AppError,
    EMPTY_OUTPUT_ERROR,
    FILE_ERROR,
    INTERNAL_ERROR,
    JSON_PARSE_ERROR,
    PROVIDER_ERROR,
    SCHEMA_VALIDATION_ERROR,
)
from extractor.provider.openai_provider import OpenAIProvider
from extractor.output import write_error_json, write_report_json
from extractor.report import make_single_case_report
from extractor.runner import _compute_file_sha256, run_batch_extraction, run_extraction, run_extraction_data
from extractor.schema_check import run_schema_check, write_schema_check_report
from extractor.snapshot import load_snapshot, write_snapshot
from extractor.json_diff import compare_json


class StrictArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ValueError(message)

    def exit(self, status: int = 0, message: str | None = None) -> None:
        if status == 0:
            raise SystemExit(0)
        raise ValueError(message or "")


def build_parser() -> argparse.ArgumentParser:
    parser = StrictArgumentParser(prog="extract")
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--input")
    run_parser.add_argument("--input-dir")
    run_parser.add_argument("--schema", required=True)
    run_parser.add_argument("--output")
    run_parser.add_argument("--output-dir")
    run_parser.add_argument("--model", default="gpt-4.1-mini")
    run_parser.add_argument("--temperature", type=float, default=0.0)
    run_parser.add_argument("--max-tokens", type=int)
    run_parser.add_argument("--fail-on-empty", action="store_true")
    run_parser.add_argument("--provider", default="openai")
    run_parser.add_argument("--simulate-provider-error", choices=("timeout", "rate_limit", "invalid_response"))
    run_parser.add_argument("--capture-output")
    run_parser.add_argument("--replay-output")
    run_parser.add_argument("--redaction-config")
    run_parser.add_argument("--report")
    run_parser.add_argument("--expected-prompt-hash")

    snapshot_parser = subparsers.add_parser("snapshot")
    snapshot_parser.add_argument("--input", required=True)
    snapshot_parser.add_argument("--schema", required=True)
    snapshot_parser.add_argument("--output", required=True)
    snapshot_parser.add_argument("--provider", default="openai")
    snapshot_parser.add_argument("--model", default="gpt-4.1-mini")
    snapshot_parser.add_argument("--simulate-provider-error", choices=("timeout", "rate_limit", "invalid_response"))
    snapshot_parser.add_argument("--report")

    compare_parser = subparsers.add_parser("compare")
    compare_parser.add_argument("--input", required=True)
    compare_parser.add_argument("--schema", required=True)
    compare_parser.add_argument("--snapshot", required=True)
    compare_parser.add_argument("--provider", default="openai")
    compare_parser.add_argument("--model", default="gpt-4.1-mini")
    compare_parser.add_argument("--simulate-provider-error", choices=("timeout", "rate_limit", "invalid_response"))

    schema_check_parser = subparsers.add_parser("schema-check")
    schema_check_parser.add_argument("--input", required=True)
    schema_check_parser.add_argument("--new-schema", required=True)
    schema_check_parser.add_argument("--output")

    diff_parser = subparsers.add_parser("diff")
    diff_parser.add_argument("--expected", required=True)
    diff_parser.add_argument("--actual", required=True)
    diff_parser.add_argument("--report")

    return parser


def _map_exit_code(error_type: str) -> int:
    if error_type in {JSON_PARSE_ERROR, SCHEMA_VALIDATION_ERROR, EMPTY_OUTPUT_ERROR}:
        return 1
    if error_type in {FILE_ERROR, PROVIDER_ERROR, INTERNAL_ERROR}:
        return 2
    return 2


def _provider_from_arg(provider_name: str, simulate_provider_error: str | None = None):
    if provider_name == "openai":
        if simulate_provider_error is None:
            return OpenAIProvider()
        return OpenAIProvider(simulate_provider_error=simulate_provider_error)
    raise AppError(FILE_ERROR, f"Failed to read file: unsupported provider: {provider_name}")


def _load_json_file_for_diff(path: str) -> object:
    try:
        raw = Path(path).read_text(encoding="utf-8")
    except Exception as exc:
        raise AppError(FILE_ERROR, f"Failed to read file: {path}") from exc
    try:
        return json.loads(raw)
    except Exception as exc:
        raise AppError(JSON_PARSE_ERROR, f"Invalid JSON file: {path}") from exc


def _print_json_output(payload: dict) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def _stage_for_error_type(error_type: str, message: str) -> str:
    if error_type == FILE_ERROR:
        if message.startswith("Failed to write file:"):
            return "internal"
        return "file_read"
    if error_type == PROVIDER_ERROR:
        return "provider_call"
    if error_type == JSON_PARSE_ERROR:
        return "json_parse"
    if error_type in {SCHEMA_VALIDATION_ERROR, EMPTY_OUTPUT_ERROR}:
        return "schema_validation"
    return "internal"


def _safe_file_hash(path: str) -> str | None:
    try:
        return _compute_file_sha256(path)
    except AppError:
        return None


def _write_run_error_artifact(
    output_path: str,
    input_path: str,
    schema_path: str,
    err: AppError,
    prompt_hash: str | None,
) -> None:
    artifact = {
        "error_type": err.error_type,
        "message": err.message,
        "stage": _stage_for_error_type(err.error_type, err.message),
        "input_hash": _safe_file_hash(input_path),
        "schema_hash": _safe_file_hash(schema_path),
        "prompt_hash": prompt_hash,
    }
    write_error_json(f"{output_path}.error.json", artifact)


def main() -> int:
    parser = build_parser()
    try:
        args = parser.parse_args()
    except ValueError:
        print("ERROR INTERNAL_ERROR Invalid command")
        return 2

    if args.command == "diff":
        try:
            expected_data = _load_json_file_for_diff(args.expected)
            actual_data = _load_json_file_for_diff(args.actual)
            raw_diffs = compare_json(actual_data, expected_data)
            if not raw_diffs:
                if args.report:
                    write_report_json(
                        args.report,
                        make_single_case_report(
                            command="diff",
                            status="SUCCESS",
                            input_file=None,
                            output_file=None,
                            error_type=None,
                        ),
                    )
                _print_json_output({"status": "PASS", "diffs": []})
                return 0
            diffs: list[dict] = []
            for diff in raw_diffs:
                item = {"type": diff["category"], "path": diff["path"]}
                if diff["category"] in {"missing", "mismatch"}:
                    item["expected_value"] = diff["expected"]
                if diff["category"] in {"extra", "mismatch"}:
                    item["actual_value"] = diff["actual"]
                diffs.append(item)
            if args.report:
                write_report_json(
                    args.report,
                    make_single_case_report(
                        command="diff",
                        status="DIFF",
                        input_file=None,
                        output_file=None,
                        error_type=None,
                    ),
                )
            _print_json_output({"status": "DIFF", "diffs": diffs})
            return 1
        except AppError as err:
            if args.report:
                try:
                    write_report_json(
                        args.report,
                        make_single_case_report(
                            command="diff",
                            status="ERROR",
                            input_file=None,
                            output_file=None,
                            error_type=err.error_type,
                        ),
                    )
                except AppError as report_err:
                    _print_json_output(
                        {"status": "ERROR", "error_type": report_err.error_type, "message": report_err.message}
                    )
                    return 2
            _print_json_output({"status": "ERROR", "error_type": err.error_type, "message": err.message})
            return 2
        except Exception:
            _print_json_output({"status": "ERROR", "error_type": INTERNAL_ERROR, "message": "Internal error"})
            return 2

    if args.command == "snapshot":
        try:
            provider = _provider_from_arg(args.provider, args.simulate_provider_error)
            result = run_extraction_data(
                input_path=args.input,
                schema_path=args.schema,
                model=args.model,
                provider=provider,
            )
            if not result.success:
                if args.report:
                    write_report_json(
                        args.report,
                        make_single_case_report(
                            command="snapshot",
                            status="ERROR",
                            input_file=args.input,
                            output_file=args.output,
                            error_type=result.error.error_type,
                        ),
                    )
                print(f"ERROR {result.error.error_type} {result.error.message}")
                return _map_exit_code(result.error.error_type)
            write_snapshot(args.output, result.data)
            if args.report:
                write_report_json(
                    args.report,
                    make_single_case_report(
                        command="snapshot",
                        status="SUCCESS",
                        input_file=args.input,
                        output_file=args.output,
                        error_type=None,
                    ),
                )
            print("SUCCESS")
            return 0
        except AppError as err:
            print(f"ERROR {err.error_type} {err.message}")
            return 2

    if args.command == "compare":
        try:
            provider = _provider_from_arg(args.provider, args.simulate_provider_error)
            result = run_extraction_data(
                input_path=args.input,
                schema_path=args.schema,
                model=args.model,
                provider=provider,
            )
            if not result.success:
                print(f"ERROR {result.error.error_type} {result.error.message}")
                return _map_exit_code(result.error.error_type)
            snapshot_data = load_snapshot(args.snapshot)
            diffs = compare_json(result.data, snapshot_data)
            if not diffs:
                print("MATCH")
                return 0
            print("DIFF")
            for diff in diffs:
                expected_text = json.dumps(diff["expected"], sort_keys=True, separators=(",", ":"))
                actual_text = json.dumps(diff["actual"], sort_keys=True, separators=(",", ":"))
                print(f"DIFF {diff['category']} {diff['path']} expected={expected_text} actual={actual_text}")
            return 1
        except AppError as err:
            print(f"ERROR {err.error_type} {err.message}")
            return 2

    if args.command == "schema-check":
        try:
            result = run_schema_check(input_path=args.input, new_schema_path=args.new_schema)
            lines = [f"SCHEMA CHECK {item.path} {item.classification}" for item in result.items]
            summary = (
                f"SCHEMA CHECK SUMMARY total={result.total} compatible={result.compatible} breaking_change={result.breaking_change}"
            )
            if args.output:
                write_schema_check_report(args.output, result)
            for line in lines:
                print(line)
            print(summary)
            if result.breaking_change > 0:
                return 1
            return 0
        except AppError as err:
            print(f"ERROR {err.error_type} {err.message}")
            if err.error_type == JSON_PARSE_ERROR:
                return 2
            return _map_exit_code(err.error_type)

    if args.command != "run":
        print("ERROR INTERNAL_ERROR Invalid command")
        return 2

    is_single_file_mode = args.input is not None and args.output is not None and args.input_dir is None and args.output_dir is None
    is_batch_mode = args.input_dir is not None and args.output_dir is not None and args.input is None and args.output is None
    if not (is_single_file_mode or is_batch_mode):
        print("ERROR INTERNAL_ERROR Invalid command")
        return 2
    if args.capture_output is not None and args.replay_output is not None:
        print("ERROR INTERNAL_ERROR Invalid command")
        return 2
    if is_batch_mode and (args.capture_output is not None or args.replay_output is not None):
        print("ERROR INTERNAL_ERROR Invalid command")
        return 2

    try:
        provider = _provider_from_arg(args.provider, args.simulate_provider_error)
    except AppError as err:
        print(f"ERROR {err.error_type} {err.message}")
        return _map_exit_code(err.error_type)
    if is_batch_mode:
        try:
            result = run_batch_extraction(
                input_dir=args.input_dir,
                schema_path=args.schema,
                output_dir=args.output_dir,
                model=args.model,
                provider=provider,
                temperature=args.temperature,
                max_tokens=args.max_tokens,
                fail_on_empty=args.fail_on_empty,
                capture_output_path=args.capture_output,
                replay_output_path=args.replay_output,
                redaction_config_path=args.redaction_config,
            )
        except AppError as err:
            print(f"ERROR {err.error_type} {err.message}")
            return _map_exit_code(err.error_type)
        print(f"total={result.total}")
        print(f"success={result.success}")
        print(f"contract_failure={result.contract_failure}")
        print(f"execution_error={result.execution_error}")
        if result.execution_error > 0:
            return 2
        if result.contract_failure > 0:
            return 1
        return 0

    result = run_extraction(
        input_path=args.input,
        schema_path=args.schema,
        output_path=args.output,
        model=args.model,
        provider=provider,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        fail_on_empty=args.fail_on_empty,
        capture_output_path=args.capture_output,
        replay_output_path=args.replay_output,
        redaction_config_path=args.redaction_config,
        expected_prompt_hash=args.expected_prompt_hash,
    )

    if result.success:
        if args.report:
            try:
                write_report_json(
                    args.report,
                    make_single_case_report(
                        command="run",
                        status="SUCCESS",
                        input_file=args.input,
                        output_file=args.output,
                        error_type=None,
                        prompt_hash=result.prompt_hash,
                        include_prompt_hash=True,
                    ),
                )
            except AppError as report_err:
                print(f"ERROR {report_err.error_type} {report_err.message}")
                return 2
        print("SUCCESS")
        return 0

    try:
        _write_run_error_artifact(
            output_path=args.output,
            input_path=args.input,
            schema_path=args.schema,
            err=result.error,
            prompt_hash=getattr(result, "prompt_hash", None),
        )
    except AppError:
        print(f"ERROR {result.error.error_type} {result.error.message}")
        return _map_exit_code(result.error.error_type)
    if args.report:
        try:
            write_report_json(
                args.report,
                make_single_case_report(
                    command="run",
                    status="ERROR",
                    input_file=args.input,
                    output_file=args.output,
                    error_type=result.error.error_type,
                    prompt_hash=result.prompt_hash,
                    include_prompt_hash=True,
                ),
            )
        except AppError as report_err:
            print(f"ERROR {report_err.error_type} {report_err.message}")
            return 2

    print(f"ERROR {result.error.error_type} {result.error.message}")
    return _map_exit_code(result.error.error_type)


if __name__ == "__main__":
    sys.exit(main())


import io
import json
import os
import sys
import tempfile
import types
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import Mock, patch

sys.modules.setdefault("openai", types.SimpleNamespace(OpenAI=object))

from extractor import cli
from extractor.errors import AppError, EMPTY_OUTPUT_ERROR, FILE_ERROR, INTERNAL_ERROR, PROVIDER_ERROR


SCHEMA_TEXT = json.dumps(
    {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "age": {"type": "number"},
            "city": {"type": "string"},
        },
        "required": ["name", "age", "city"],
    }
)


class FakeProvider:
    name = "test"

    def __init__(self, *args, **kwargs):
        pass

    def generate(self, prompt: str, model: str, temperature: float, max_tokens: int | None) -> str:
        if "BADJSON" in prompt:
            return "not-json"
        if "SCHEMAFAIL" in prompt:
            return json.dumps({"name": "John", "city": "Bangalore"})
        if "PROVIDERERR" in prompt:
            raise AppError(PROVIDER_ERROR, "Provider request failed")
        if "Alpha" in prompt:
            return json.dumps({"name": "Alpha", "age": 11, "city": "Bangalore"})
        if "Beta" in prompt:
            return json.dumps({"name": "Beta", "age": 12, "city": "Delhi"})
        return json.dumps({"name": "John Doe", "age": 30, "city": "Bangalore"})


class TestCliSlice2(unittest.TestCase):
    def _run_cli(self, argv: list[str], provider_class=FakeProvider):
        out = io.StringIO()
        with patch("extractor.cli.OpenAIProvider", provider_class), patch("sys.argv", argv), redirect_stdout(out):
            exit_code = cli.main()
        return exit_code, out.getvalue()

    def _write_schema(self, root: Path) -> Path:
        path = root / "schema.json"
        path.write_text(SCHEMA_TEXT, encoding="utf-8")
        return path

    def test_batch_all_success(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            input_dir = root / "inputs"
            output_dir = root / "outputs"
            input_dir.mkdir()
            output_dir.mkdir()
            (input_dir / "a.txt").write_text("Alpha", encoding="utf-8")
            (input_dir / "b.txt").write_text("Beta", encoding="utf-8")
            schema = self._write_schema(root)

            exit_code, stdout = self._run_cli(
                [
                    "extract",
                    "run",
                    "--input-dir",
                    str(input_dir),
                    "--schema",
                    str(schema),
                    "--output-dir",
                    str(output_dir),
                ]
            )

            self.assertEqual(exit_code, 0)
            self.assertEqual(stdout, "total=2\nsuccess=2\ncontract_failure=0\nexecution_error=0\n")
            self.assertTrue((output_dir / "a.json").exists())
            self.assertTrue((output_dir / "b.json").exists())

    def test_batch_mixed_success_and_contract_failure(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            input_dir = root / "inputs"
            output_dir = root / "outputs"
            input_dir.mkdir()
            output_dir.mkdir()
            (input_dir / "ok.txt").write_text("Alpha", encoding="utf-8")
            (input_dir / "bad.txt").write_text("BADJSON", encoding="utf-8")
            schema = self._write_schema(root)

            exit_code, stdout = self._run_cli(
                [
                    "extract",
                    "run",
                    "--input-dir",
                    str(input_dir),
                    "--schema",
                    str(schema),
                    "--output-dir",
                    str(output_dir),
                ]
            )

            self.assertEqual(exit_code, 1)
            self.assertEqual(stdout, "total=2\nsuccess=1\ncontract_failure=1\nexecution_error=0\n")
            self.assertTrue((output_dir / "ok.json").exists())
            self.assertFalse((output_dir / "bad.json").exists())

    def test_batch_with_execution_error(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            input_dir = root / "inputs"
            output_dir = root / "outputs"
            input_dir.mkdir()
            output_dir.mkdir()
            (input_dir / "ok.txt").write_text("Alpha", encoding="utf-8")
            (input_dir / "err.txt").write_text("PROVIDERERR", encoding="utf-8")
            schema = self._write_schema(root)

            exit_code, stdout = self._run_cli(
                [
                    "extract",
                    "run",
                    "--input-dir",
                    str(input_dir),
                    "--schema",
                    str(schema),
                    "--output-dir",
                    str(output_dir),
                ]
            )

            self.assertEqual(exit_code, 2)
            self.assertEqual(stdout, "total=2\nsuccess=1\ncontract_failure=0\nexecution_error=1\n")
            self.assertTrue((output_dir / "ok.json").exists())
            self.assertFalse((output_dir / "err.json").exists())

    def test_batch_no_silent_partial_success_contract_stress(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            input_dir = root / "inputs"
            output_dir = root / "outputs"
            input_dir.mkdir()
            output_dir.mkdir()
            (input_dir / "ok.txt").write_text("Alpha", encoding="utf-8")
            (input_dir / "bad_1.txt").write_text("BADJSON", encoding="utf-8")
            (input_dir / "bad_2.txt").write_text("BADJSON", encoding="utf-8")
            schema = self._write_schema(root)

            exit_code, stdout = self._run_cli(
                [
                    "extract",
                    "run",
                    "--input-dir",
                    str(input_dir),
                    "--schema",
                    str(schema),
                    "--output-dir",
                    str(output_dir),
                ]
            )

            self.assertEqual(exit_code, 1)
            self.assertEqual(stdout, "total=3\nsuccess=1\ncontract_failure=2\nexecution_error=0\n")
            self.assertTrue((output_dir / "ok.json").exists())
            self.assertFalse((output_dir / "bad_1.json").exists())
            self.assertFalse((output_dir / "bad_2.json").exists())

    def test_argument_validation_mutual_exclusivity(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            input_file = root / "input.txt"
            input_file.write_text("Alpha", encoding="utf-8")
            input_dir = root / "inputs"
            input_dir.mkdir()
            output_file = root / "output.json"
            schema = self._write_schema(root)

            exit_code, stdout = self._run_cli(
                [
                    "extract",
                    "run",
                    "--input",
                    str(input_file),
                    "--input-dir",
                    str(input_dir),
                    "--schema",
                    str(schema),
                    "--output",
                    str(output_file),
                ]
            )

            self.assertEqual(exit_code, 2)
            self.assertEqual(stdout, "ERROR INTERNAL_ERROR Invalid command\n")

    def test_argument_validation_mixed_forms(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            input_file = root / "input.txt"
            input_file.write_text("Alpha", encoding="utf-8")
            input_dir = root / "inputs"
            input_dir.mkdir()
            output_file = root / "output.json"
            output_dir = root / "outputs"
            output_dir.mkdir()
            schema = self._write_schema(root)

            cases = [
                [
                    "extract",
                    "run",
                    "--input",
                    str(input_file),
                    "--schema",
                    str(schema),
                    "--output-dir",
                    str(output_dir),
                ],
                [
                    "extract",
                    "run",
                    "--input-dir",
                    str(input_dir),
                    "--schema",
                    str(schema),
                    "--output",
                    str(output_file),
                ],
                [
                    "extract",
                    "run",
                    "--input",
                    str(input_file),
                    "--schema",
                    str(schema),
                    "--output",
                    str(output_file),
                    "--output-dir",
                    str(output_dir),
                ],
            ]

            for argv in cases:
                exit_code, stdout = self._run_cli(argv)
                self.assertEqual(exit_code, 2)
                self.assertEqual(stdout, "ERROR INTERNAL_ERROR Invalid command\n")

    def test_batch_exit_code_precedence_execution_over_contract(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            input_dir = root / "inputs"
            output_dir = root / "outputs"
            input_dir.mkdir()
            output_dir.mkdir()
            (input_dir / "bad.txt").write_text("BADJSON", encoding="utf-8")
            (input_dir / "err.txt").write_text("PROVIDERERR", encoding="utf-8")
            schema = self._write_schema(root)

            exit_code, stdout = self._run_cli(
                [
                    "extract",
                    "run",
                    "--input-dir",
                    str(input_dir),
                    "--schema",
                    str(schema),
                    "--output-dir",
                    str(output_dir),
                ]
            )

            self.assertEqual(exit_code, 2)
            self.assertEqual(stdout, "total=2\nsuccess=0\ncontract_failure=1\nexecution_error=1\n")

    def test_batch_nonexistent_input_dir_returns_deterministic_error(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            missing_input_dir = root / "missing"
            output_dir = root / "outputs"
            output_dir.mkdir()
            schema = self._write_schema(root)

            exit_code, stdout = self._run_cli(
                [
                    "extract",
                    "run",
                    "--input-dir",
                    str(missing_input_dir),
                    "--schema",
                    str(schema),
                    "--output-dir",
                    str(output_dir),
                ]
            )

            self.assertEqual(exit_code, 2)
            self.assertEqual(stdout, f"ERROR FILE_ERROR Failed to read file: {missing_input_dir}\n")

    def test_batch_duplicate_stems_across_extensions_fails_deterministically(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            input_dir = root / "inputs"
            output_dir = root / "outputs"
            input_dir.mkdir()
            output_dir.mkdir()
            (input_dir / "a.txt").write_text("Alpha", encoding="utf-8")
            (input_dir / "a.json").write_text(json.dumps({"x": "Beta"}), encoding="utf-8")
            schema = self._write_schema(root)

            exit_code, stdout = self._run_cli(
                [
                    "extract",
                    "run",
                    "--input-dir",
                    str(input_dir),
                    "--schema",
                    str(schema),
                    "--output-dir",
                    str(output_dir),
                ]
            )

            self.assertEqual(exit_code, 2)
            self.assertEqual(stdout, "ERROR FILE_ERROR Failed to read file: duplicate stems: a\n")
            self.assertFalse((output_dir / "a.json").exists())

    def test_single_file_mode_unchanged(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            input_file = root / "input.txt"
            output_file = root / "output.json"
            input_file.write_text("John Doe is 30 years old and lives in Bangalore.", encoding="utf-8")
            schema = self._write_schema(root)

            exit_code, stdout = self._run_cli(
                [
                    "extract",
                    "run",
                    "--input",
                    str(input_file),
                    "--schema",
                    str(schema),
                    "--output",
                    str(output_file),
                ]
            )

            self.assertEqual(exit_code, 0)
            self.assertEqual(stdout, "SUCCESS\n")
            self.assertTrue(output_file.exists())

    def test_fail_on_empty_returns_contract_failure(self):
        class EmptyProvider:
            name = "test"

            def generate(self, prompt: str, model: str, temperature: float, max_tokens: int | None) -> str:
                return json.dumps({"name": "", "age": None, "city": ""})

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            input_file = root / "input.md"
            output_file = root / "output.json"
            schema = root / "schema.json"
            input_file.write_text("x", encoding="utf-8")
            schema.write_text(
                json.dumps(
                    {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "age": {"type": ["number", "null"]},
                            "city": {"type": "string"},
                        },
                        "required": ["name", "age", "city"],
                    }
                ),
                encoding="utf-8",
            )

            exit_code, stdout = self._run_cli(
                [
                    "extract",
                    "run",
                    "--input",
                    str(input_file),
                    "--schema",
                    str(schema),
                    "--output",
                    str(output_file),
                    "--fail-on-empty",
                ],
                provider_class=EmptyProvider,
            )

            self.assertEqual(exit_code, 1)
            self.assertEqual(stdout, "ERROR EMPTY_OUTPUT_ERROR Semantically empty output\n")

    def test_run_simulate_provider_timeout_exit_2(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            input_file = root / "input.txt"
            output_file = root / "output.json"
            input_file.write_text("John Doe is 30 years old and lives in Bangalore.", encoding="utf-8")
            schema = self._write_schema(root)
            out = io.StringIO()
            with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=False), patch("sys.argv", [
                "extract",
                "run",
                "--input",
                str(input_file),
                "--schema",
                str(schema),
                "--output",
                str(output_file),
                "--simulate-provider-error",
                "timeout",
            ]), redirect_stdout(out):
                exit_code = cli.main()
            self.assertEqual(exit_code, 2)
            self.assertEqual(out.getvalue(), "ERROR PROVIDER_ERROR Provider timeout (simulated)\n")

    def test_run_simulate_provider_rate_limit_exit_2(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            input_file = root / "input.txt"
            output_file = root / "output.json"
            input_file.write_text("John Doe is 30 years old and lives in Bangalore.", encoding="utf-8")
            schema = self._write_schema(root)
            out = io.StringIO()
            with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=False), patch("sys.argv", [
                "extract",
                "run",
                "--input",
                str(input_file),
                "--schema",
                str(schema),
                "--output",
                str(output_file),
                "--simulate-provider-error",
                "rate_limit",
            ]), redirect_stdout(out):
                exit_code = cli.main()
            self.assertEqual(exit_code, 2)
            self.assertEqual(out.getvalue(), "ERROR PROVIDER_ERROR Provider rate limit (simulated)\n")

    def test_run_simulate_provider_invalid_response_exit_2(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            input_file = root / "input.txt"
            output_file = root / "output.json"
            input_file.write_text("John Doe is 30 years old and lives in Bangalore.", encoding="utf-8")
            schema = self._write_schema(root)
            out = io.StringIO()
            with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=False), patch("sys.argv", [
                "extract",
                "run",
                "--input",
                str(input_file),
                "--schema",
                str(schema),
                "--output",
                str(output_file),
                "--simulate-provider-error",
                "invalid_response",
            ]), redirect_stdout(out):
                exit_code = cli.main()
            self.assertEqual(exit_code, 2)
            self.assertEqual(out.getvalue(), "ERROR PROVIDER_ERROR Provider invalid response (simulated)\n")

    def test_run_uses_provider_resolver_path(self):
        provider = FakeProvider()
        resolver = Mock(return_value=provider)
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            input_file = root / "input.txt"
            output_file = root / "output.json"
            input_file.write_text("John Doe is 30 years old and lives in Bangalore.", encoding="utf-8")
            schema = self._write_schema(root)
            out = io.StringIO()
            with patch("extractor.cli._provider_from_arg", resolver), patch("sys.argv", [
                "extract",
                "run",
                "--input",
                str(input_file),
                "--schema",
                str(schema),
                "--output",
                str(output_file),
            ]), redirect_stdout(out):
                exit_code = cli.main()
            self.assertEqual(exit_code, 0)
            self.assertEqual(out.getvalue(), "SUCCESS\n")
            resolver.assert_called_once_with("openai", None)

    def test_run_simulation_without_api_key_uses_simulated_error(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            input_file = root / "input.txt"
            output_file = root / "output.json"
            input_file.write_text("John Doe is 30 years old and lives in Bangalore.", encoding="utf-8")
            schema = self._write_schema(root)
            out = io.StringIO()
            with patch.dict(os.environ, {}, clear=True), patch("sys.argv", [
                "extract",
                "run",
                "--input",
                str(input_file),
                "--schema",
                str(schema),
                "--output",
                str(output_file),
                "--simulate-provider-error",
                "timeout",
            ]), redirect_stdout(out):
                exit_code = cli.main()
            self.assertEqual(exit_code, 2)
            self.assertEqual(out.getvalue(), "ERROR PROVIDER_ERROR Provider timeout (simulated)\n")

    def test_run_replay_success_output_matches_expected_json(self):
        class RaiseIfCalledProvider:
            name = "test"

            def __init__(self, *args, **kwargs):
                pass

            def generate(self, prompt: str, model: str, temperature: float, max_tokens: int | None) -> str:
                raise AssertionError("provider should not be called")

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            input_file = root / "input.txt"
            output_file = root / "output.json"
            replay_file = root / "replay.txt"
            schema = self._write_schema(root)
            input_file.write_text("ignored", encoding="utf-8")
            replay_file.write_text(json.dumps({"name": "John Doe", "age": 30, "city": "Bangalore"}), encoding="utf-8")
            code, out = self._run_cli(
                [
                    "extract",
                    "run",
                    "--input",
                    str(input_file),
                    "--schema",
                    str(schema),
                    "--output",
                    str(output_file),
                    "--replay-output",
                    str(replay_file),
                ],
                provider_class=RaiseIfCalledProvider,
            )
            self.assertEqual(code, 0)
            self.assertEqual(out, "SUCCESS\n")
            data = json.loads(output_file.read_text(encoding="utf-8"))
            self.assertEqual(data["name"], "John Doe")
            self.assertEqual(data["age"], 30)
            self.assertEqual(data["city"], "Bangalore")

    def test_run_replay_invalid_json_returns_contract_failure(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            input_file = root / "input.txt"
            output_file = root / "output.json"
            replay_file = root / "replay.txt"
            schema = self._write_schema(root)
            input_file.write_text("ignored", encoding="utf-8")
            replay_file.write_text("not-json", encoding="utf-8")
            code, out = self._run_cli(
                [
                    "extract",
                    "run",
                    "--input",
                    str(input_file),
                    "--schema",
                    str(schema),
                    "--output",
                    str(output_file),
                    "--replay-output",
                    str(replay_file),
                ]
            )
            self.assertEqual(code, 1)
            self.assertEqual(out, "ERROR JSON_PARSE_ERROR Invalid JSON returned by model\n")

    def test_run_replay_schema_invalid_returns_contract_failure(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            input_file = root / "input.txt"
            output_file = root / "output.json"
            replay_file = root / "replay.txt"
            schema = self._write_schema(root)
            input_file.write_text("ignored", encoding="utf-8")
            replay_file.write_text(json.dumps({"name": "John Doe", "city": "Bangalore"}), encoding="utf-8")
            code, out = self._run_cli(
                [
                    "extract",
                    "run",
                    "--input",
                    str(input_file),
                    "--schema",
                    str(schema),
                    "--output",
                    str(output_file),
                    "--replay-output",
                    str(replay_file),
                ]
            )
            self.assertEqual(code, 1)
            self.assertEqual(out, "ERROR SCHEMA_VALIDATION_ERROR Missing required field: age\n")

    def test_run_replay_missing_file_returns_execution_error(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            input_file = root / "input.txt"
            output_file = root / "output.json"
            replay_file = root / "missing.txt"
            schema = self._write_schema(root)
            input_file.write_text("ignored", encoding="utf-8")
            code, out = self._run_cli(
                [
                    "extract",
                    "run",
                    "--input",
                    str(input_file),
                    "--schema",
                    str(schema),
                    "--output",
                    str(output_file),
                    "--replay-output",
                    str(replay_file),
                ]
            )
            self.assertEqual(code, 2)
            self.assertEqual(out, f"ERROR FILE_ERROR Failed to read file: {replay_file}\n")

    def test_run_capture_writes_exact_raw_response(self):
        class RawProvider:
            name = "test"

            def __init__(self, *args, **kwargs):
                pass

            def generate(self, prompt: str, model: str, temperature: float, max_tokens: int | None) -> str:
                return '{ "name":"John Doe","age":30,"city":"Bangalore" }\n'

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            input_file = root / "input.txt"
            output_file = root / "output.json"
            capture_file = root / "capture.txt"
            schema = self._write_schema(root)
            input_file.write_text("ignored", encoding="utf-8")
            code, out = self._run_cli(
                [
                    "extract",
                    "run",
                    "--input",
                    str(input_file),
                    "--schema",
                    str(schema),
                    "--output",
                    str(output_file),
                    "--capture-output",
                    str(capture_file),
                ],
                provider_class=RawProvider,
            )
            self.assertEqual(code, 0)
            self.assertEqual(out, "SUCCESS\n")
            self.assertEqual(capture_file.read_text(encoding="utf-8"), '{ "name":"John Doe","age":30,"city":"Bangalore" }\n')

    def test_run_capture_write_failure_returns_execution_error(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            input_file = root / "input.txt"
            output_file = root / "output.json"
            capture_file = root / "missing" / "capture.txt"
            schema = self._write_schema(root)
            input_file.write_text("ignored", encoding="utf-8")
            code, out = self._run_cli(
                [
                    "extract",
                    "run",
                    "--input",
                    str(input_file),
                    "--schema",
                    str(schema),
                    "--output",
                    str(output_file),
                    "--capture-output",
                    str(capture_file),
                ]
            )
            self.assertEqual(code, 2)
            self.assertEqual(out, f"ERROR FILE_ERROR Failed to write file: {capture_file}\n")

    def test_run_rejects_both_capture_and_replay_flags(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            input_file = root / "input.txt"
            output_file = root / "output.json"
            replay_file = root / "replay.txt"
            capture_file = root / "capture.txt"
            schema = self._write_schema(root)
            input_file.write_text("ignored", encoding="utf-8")
            replay_file.write_text("{}", encoding="utf-8")
            code, out = self._run_cli(
                [
                    "extract",
                    "run",
                    "--input",
                    str(input_file),
                    "--schema",
                    str(schema),
                    "--output",
                    str(output_file),
                    "--capture-output",
                    str(capture_file),
                    "--replay-output",
                    str(replay_file),
                ]
            )
            self.assertEqual(code, 2)
            self.assertEqual(out, "ERROR INTERNAL_ERROR Invalid command\n")

    def test_run_rejects_batch_mode_with_capture_or_replay(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            input_dir = root / "inputs"
            output_dir = root / "outputs"
            replay_file = root / "replay.txt"
            capture_file = root / "capture.txt"
            input_dir.mkdir()
            output_dir.mkdir()
            (input_dir / "a.txt").write_text("Alpha", encoding="utf-8")
            schema = self._write_schema(root)
            replay_file.write_text("{}", encoding="utf-8")

            code_capture, out_capture = self._run_cli(
                [
                    "extract",
                    "run",
                    "--input-dir",
                    str(input_dir),
                    "--schema",
                    str(schema),
                    "--output-dir",
                    str(output_dir),
                    "--capture-output",
                    str(capture_file),
                ]
            )
            self.assertEqual(code_capture, 2)
            self.assertEqual(out_capture, "ERROR INTERNAL_ERROR Invalid command\n")

            code_replay, out_replay = self._run_cli(
                [
                    "extract",
                    "run",
                    "--input-dir",
                    str(input_dir),
                    "--schema",
                    str(schema),
                    "--output-dir",
                    str(output_dir),
                    "--replay-output",
                    str(replay_file),
                ]
            )
            self.assertEqual(code_replay, 2)
            self.assertEqual(out_replay, "ERROR INTERNAL_ERROR Invalid command\n")

    def test_single_run_writes_deterministic_metadata_artifact(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            input_file = root / "input.txt"
            output_file = root / "output.json"
            schema = self._write_schema(root)
            input_file.write_text("John Doe is 30 years old and lives in Bangalore.", encoding="utf-8")

            exit_code, stdout = self._run_cli(
                [
                    "extract",
                    "run",
                    "--input",
                    str(input_file),
                    "--schema",
                    str(schema),
                    "--output",
                    str(output_file),
                ]
            )

            self.assertEqual(exit_code, 0)
            self.assertEqual(stdout, "SUCCESS\n")
            meta_path = Path(f"{output_file}.meta.json")
            self.assertTrue(meta_path.exists())

            metadata = json.loads(meta_path.read_text(encoding="utf-8"))
            self.assertEqual(
                set(metadata.keys()),
                {
                    "input_hash",
                    "schema_hash",
                    "provider",
                    "model",
                    "input_file",
                    "temperature",
                    "prompt_hash",
                    "redaction_applied",
                    "timestamp",
                },
            )
            self.assertEqual(metadata["provider"], "test")
            self.assertEqual(metadata["model"], "gpt-4.1-mini")
            self.assertFalse(metadata["redaction_applied"])
            self.assertRegex(metadata["timestamp"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

            meta_2_path = root / "output_2.json.meta.json"
            exit_code_2, _ = self._run_cli(
                [
                    "extract",
                    "run",
                    "--input",
                    str(input_file),
                    "--schema",
                    str(schema),
                    "--output",
                    str(root / "output_2.json"),
                ]
            )
            self.assertEqual(exit_code_2, 0)
            metadata_2 = json.loads(meta_2_path.read_text(encoding="utf-8"))
            self.assertEqual(metadata["input_hash"], metadata_2["input_hash"])
            self.assertEqual(metadata["schema_hash"], metadata_2["schema_hash"])
            self.assertEqual(metadata["prompt_hash"], metadata_2["prompt_hash"])

            output = json.loads(output_file.read_text(encoding="utf-8"))
            self.assertEqual(output["name"], "John Doe")
            self.assertEqual(output["age"], 30)
            self.assertEqual(output["city"], "Bangalore")
            self.assertNotIn("_meta", output)
            self.assertFalse(Path(f"{output_file}.error.json").exists())

    def test_single_run_metadata_write_failure_returns_file_error(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            input_file = root / "input.txt"
            output_file = root / "outdir"
            output_file.mkdir()
            schema = self._write_schema(root)
            input_file.write_text("Alpha", encoding="utf-8")

            exit_code, stdout = self._run_cli(
                [
                    "extract",
                    "run",
                    "--input",
                    str(input_file),
                    "--schema",
                    str(schema),
                    "--output",
                    str(output_file),
                ]
            )
            self.assertEqual(exit_code, 2)
            self.assertEqual(stdout, f"ERROR FILE_ERROR Failed to write file: {output_file}\n")

    def test_single_run_metadata_hash_read_failure_returns_file_error(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            input_file = root / "input.txt"
            output_file = root / "output.json"
            schema = self._write_schema(root)
            input_file.write_text("Alpha", encoding="utf-8")

            with patch("pathlib.Path.read_bytes", side_effect=PermissionError("denied")):
                exit_code, stdout = self._run_cli(
                    [
                        "extract",
                        "run",
                        "--input",
                        str(input_file),
                        "--schema",
                        str(schema),
                        "--output",
                        str(output_file),
                    ]
                )

            self.assertEqual(exit_code, 2)
            self.assertEqual(stdout, f"ERROR FILE_ERROR Failed to read file: {input_file}\n")

    def test_single_run_failures_do_not_write_metadata(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            schema = self._write_schema(root)

            cases = [
                {
                    "name": "json_parse_failure",
                    "input_text": "BADJSON",
                    "expected_exit": 1,
                    "expected_out": "ERROR JSON_PARSE_ERROR Invalid JSON returned by model\n",
                },
                {
                    "name": "schema_failure",
                    "input_text": "SCHEMAFAIL",
                    "expected_exit": 1,
                    "expected_out": "ERROR SCHEMA_VALIDATION_ERROR Missing required field: age\n",
                },
                {
                    "name": "provider_failure",
                    "input_text": "PROVIDERERR",
                    "expected_exit": 2,
                    "expected_out": "ERROR PROVIDER_ERROR Provider request failed\n",
                },
                {
                    "name": "file_failure",
                    "input_text": None,
                    "expected_exit": 2,
                    "expected_out": None,
                },
            ]

            for case in cases:
                output_path = root / f"{case['name']}.json"
                meta_path = Path(f"{output_path}.meta.json")
                if case["name"] == "file_failure":
                    missing_input = root / "missing.txt"
                    exit_code, stdout = self._run_cli(
                        [
                            "extract",
                            "run",
                            "--input",
                            str(missing_input),
                            "--schema",
                            str(schema),
                            "--output",
                            str(output_path),
                        ]
                    )
                    self.assertEqual(exit_code, case["expected_exit"])
                    self.assertTrue(stdout.startswith("ERROR FILE_ERROR Failed to read file:"))
                else:
                    input_file = root / f"{case['name']}.txt"
                    input_file.write_text(case["input_text"], encoding="utf-8")
                    exit_code, stdout = self._run_cli(
                        [
                            "extract",
                            "run",
                            "--input",
                            str(input_file),
                            "--schema",
                            str(schema),
                            "--output",
                            str(output_path),
                        ]
                    )
                    self.assertEqual(exit_code, case["expected_exit"])
                    self.assertEqual(stdout, case["expected_out"])

                self.assertFalse(meta_path.exists())

    def test_single_run_failure_writes_error_artifact_with_exact_fields(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            input_file = root / "input.txt"
            output_file = root / "output.json"
            schema = self._write_schema(root)
            input_file.write_text("PROVIDERERR", encoding="utf-8")

            exit_code, stdout = self._run_cli(
                [
                    "extract",
                    "run",
                    "--input",
                    str(input_file),
                    "--schema",
                    str(schema),
                    "--output",
                    str(output_file),
                ]
            )
            self.assertEqual(exit_code, 2)
            self.assertEqual(stdout, "ERROR PROVIDER_ERROR Provider request failed\n")

            error_path = Path(f"{output_file}.error.json")
            self.assertTrue(error_path.exists())
            payload = json.loads(error_path.read_text(encoding="utf-8"))
            self.assertEqual(
                set(payload.keys()),
                {"error_type", "message", "stage", "input_hash", "schema_hash", "prompt_hash"},
            )
            self.assertEqual(payload["error_type"], "PROVIDER_ERROR")
            self.assertEqual(payload["message"], "Provider request failed")
            self.assertEqual(payload["stage"], "provider_call")
            self.assertIsInstance(payload["input_hash"], str)
            self.assertIsInstance(payload["schema_hash"], str)
            self.assertIsInstance(payload["prompt_hash"], str)

    def test_error_artifact_is_byte_identical_for_identical_failure(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            input_file = root / "input.txt"
            schema = self._write_schema(root)
            output_file_1 = root / "err1.json"
            output_file_2 = root / "err2.json"
            input_file.write_text("PROVIDERERR", encoding="utf-8")

            code_1, out_1 = self._run_cli(
                [
                    "extract",
                    "run",
                    "--input",
                    str(input_file),
                    "--schema",
                    str(schema),
                    "--output",
                    str(output_file_1),
                ]
            )
            code_2, out_2 = self._run_cli(
                [
                    "extract",
                    "run",
                    "--input",
                    str(input_file),
                    "--schema",
                    str(schema),
                    "--output",
                    str(output_file_2),
                ]
            )

            self.assertEqual(code_1, 2)
            self.assertEqual(code_2, 2)
            self.assertEqual(out_1, "ERROR PROVIDER_ERROR Provider request failed\n")
            self.assertEqual(out_2, "ERROR PROVIDER_ERROR Provider request failed\n")
            self.assertEqual(
                Path(f"{output_file_1}.error.json").read_bytes(),
                Path(f"{output_file_2}.error.json").read_bytes(),
            )

    def test_single_run_error_artifact_stage_mapping(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            schema = self._write_schema(root)

            cases = [
                ("json_parse", "BADJSON", "JSON_PARSE_ERROR", "json_parse", 1),
                ("schema_validation", "SCHEMAFAIL", "SCHEMA_VALIDATION_ERROR", "schema_validation", 1),
                ("provider_call", "PROVIDERERR", "PROVIDER_ERROR", "provider_call", 2),
            ]
            for suffix, input_text, expected_error_type, expected_stage, expected_code in cases:
                input_file = root / f"{suffix}.txt"
                output_file = root / f"{suffix}.json"
                input_file.write_text(input_text, encoding="utf-8")
                code, _ = self._run_cli(
                    [
                        "extract",
                        "run",
                        "--input",
                        str(input_file),
                        "--schema",
                        str(schema),
                        "--output",
                        str(output_file),
                    ]
                )
                self.assertEqual(code, expected_code)
                payload = json.loads(Path(f"{output_file}.error.json").read_text(encoding="utf-8"))
                self.assertEqual(payload["error_type"], expected_error_type)
                self.assertEqual(payload["stage"], expected_stage)

    def test_single_run_error_artifact_file_read_stage_and_null_hash(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            output_file = root / "missing-output.json"
            schema = self._write_schema(root)
            missing_input = root / "missing.txt"

            code, out = self._run_cli(
                [
                    "extract",
                    "run",
                    "--input",
                    str(missing_input),
                    "--schema",
                    str(schema),
                    "--output",
                    str(output_file),
                ]
            )
            self.assertEqual(code, 2)
            self.assertEqual(out, f"ERROR FILE_ERROR Failed to read file: {missing_input}\n")
            payload = json.loads(Path(f"{output_file}.error.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["error_type"], "FILE_ERROR")
            self.assertEqual(payload["stage"], "file_read")
            self.assertIsNone(payload["input_hash"])
            self.assertIsInstance(payload["schema_hash"], str)
            self.assertIsNone(payload["prompt_hash"])

    def test_expected_prompt_hash_mismatch_fails_before_provider_call(self):
        class RaiseIfCalledProvider:
            name = "test"

            def __init__(self, *args, **kwargs):
                pass

            def generate(self, prompt: str, model: str, temperature: float, max_tokens: int | None) -> str:
                raise AssertionError("provider should not be called")

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            input_file = root / "input.txt"
            output_file = root / "output.json"
            schema = self._write_schema(root)
            input_file.write_text("Alpha", encoding="utf-8")
            code, out = self._run_cli(
                [
                    "extract",
                    "run",
                    "--input",
                    str(input_file),
                    "--schema",
                    str(schema),
                    "--output",
                    str(output_file),
                    "--expected-prompt-hash",
                    "not-the-right-hash",
                ],
                provider_class=RaiseIfCalledProvider,
            )
            self.assertEqual(code, 2)
            self.assertEqual(out, "ERROR INTERNAL_ERROR Prompt hash mismatch\n")
            payload = json.loads(Path(f"{output_file}.error.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["error_type"], "INTERNAL_ERROR")
            self.assertEqual(payload["message"], "Prompt hash mismatch")
            self.assertIsInstance(payload["prompt_hash"], str)

    def test_single_run_error_artifact_internal_stage(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            input_file = root / "input.txt"
            schema = self._write_schema(root)
            output_file = root / "internal.json"
            input_file.write_text("Alpha", encoding="utf-8")
            fake_result = types.SimpleNamespace(success=False, error=AppError(INTERNAL_ERROR, "Internal error"))

            with patch("extractor.cli.run_extraction", return_value=fake_result):
                code, out = self._run_cli(
                    [
                        "extract",
                        "run",
                        "--input",
                        str(input_file),
                        "--schema",
                        str(schema),
                        "--output",
                        str(output_file),
                    ]
                )
            self.assertEqual(code, 2)
            self.assertEqual(out, "ERROR INTERNAL_ERROR Internal error\n")
            payload = json.loads(Path(f"{output_file}.error.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["error_type"], "INTERNAL_ERROR")
            self.assertEqual(payload["stage"], "internal")

    def test_single_run_error_artifact_empty_output_preserves_type_and_stage(self):
        class EmptyProvider:
            name = "test"

            def __init__(self, *args, **kwargs):
                pass

            def generate(self, prompt: str, model: str, temperature: float, max_tokens: int | None) -> str:
                return json.dumps({"name": "", "age": None, "city": ""})

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            input_file = root / "input.txt"
            output_file = root / "empty.json"
            schema = root / "schema.json"
            input_file.write_text("x", encoding="utf-8")
            schema.write_text(
                json.dumps(
                    {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "age": {"type": ["number", "null"]},
                            "city": {"type": "string"},
                        },
                        "required": ["name", "age", "city"],
                    }
                ),
                encoding="utf-8",
            )

            code, out = self._run_cli(
                [
                    "extract",
                    "run",
                    "--input",
                    str(input_file),
                    "--schema",
                    str(schema),
                    "--output",
                    str(output_file),
                    "--fail-on-empty",
                ],
                provider_class=EmptyProvider,
            )
            self.assertEqual(code, 1)
            self.assertEqual(out, "ERROR EMPTY_OUTPUT_ERROR Semantically empty output\n")
            payload = json.loads(Path(f"{output_file}.error.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["error_type"], EMPTY_OUTPUT_ERROR)
            self.assertEqual(payload["stage"], "schema_validation")
            self.assertIsInstance(payload["prompt_hash"], str)

    def test_single_run_error_artifact_hash_read_failure_sets_null(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            input_file = root / "input.txt"
            output_file = root / "provider-error.json"
            schema = self._write_schema(root)
            input_file.write_text("PROVIDERERR", encoding="utf-8")

            with patch("extractor.cli._compute_file_sha256", side_effect=AppError(FILE_ERROR, "Failed to read file: x")):
                code, out = self._run_cli(
                    [
                        "extract",
                        "run",
                        "--input",
                        str(input_file),
                        "--schema",
                        str(schema),
                        "--output",
                        str(output_file),
                    ]
                )
            self.assertEqual(code, 2)
            self.assertEqual(out, "ERROR PROVIDER_ERROR Provider request failed\n")
            payload = json.loads(Path(f"{output_file}.error.json").read_text(encoding="utf-8"))
            self.assertIsNone(payload["input_hash"])
            self.assertIsNone(payload["schema_hash"])

    def test_single_run_error_artifact_write_failure_returns_file_error(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            input_file = root / "input.txt"
            output_file = root / "provider-error.json"
            schema = self._write_schema(root)
            input_file.write_text("PROVIDERERR", encoding="utf-8")

            with patch("extractor.cli.write_error_json", side_effect=AppError(FILE_ERROR, "Failed to write file: bad.error.json")):
                code, out = self._run_cli(
                    [
                        "extract",
                        "run",
                        "--input",
                        str(input_file),
                        "--schema",
                        str(schema),
                        "--output",
                        str(output_file),
                    ]
                )
            self.assertEqual(code, 2)
            self.assertEqual(out, "ERROR PROVIDER_ERROR Provider request failed\n")

    def test_json_parse_error_with_artifact_write_failure_preserves_original_exit_and_output(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            input_file = root / "input.txt"
            output_file = root / "json-parse-error.json"
            schema = self._write_schema(root)
            input_file.write_text("BADJSON", encoding="utf-8")

            with patch("extractor.cli.write_error_json", side_effect=AppError(FILE_ERROR, "Failed to write file: bad.error.json")):
                code, out = self._run_cli(
                    [
                        "extract",
                        "run",
                        "--input",
                        str(input_file),
                        "--schema",
                        str(schema),
                        "--output",
                        str(output_file),
                    ]
                )
            self.assertEqual(code, 1)
            self.assertEqual(out, "ERROR JSON_PARSE_ERROR Invalid JSON returned by model\n")

    def test_schema_validation_error_with_artifact_write_failure_preserves_original_exit_and_output(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            input_file = root / "input.txt"
            output_file = root / "schema-validation-error.json"
            schema = self._write_schema(root)
            input_file.write_text("SCHEMAFAIL", encoding="utf-8")

            with patch("extractor.cli.write_error_json", side_effect=AppError(FILE_ERROR, "Failed to write file: bad.error.json")):
                code, out = self._run_cli(
                    [
                        "extract",
                        "run",
                        "--input",
                        str(input_file),
                        "--schema",
                        str(schema),
                        "--output",
                        str(output_file),
                    ]
                )
            self.assertEqual(code, 1)
            self.assertEqual(out, "ERROR SCHEMA_VALIDATION_ERROR Missing required field: age\n")

    def test_write_related_file_error_maps_stage_internal(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            input_file = root / "input.txt"
            output_file = root / "write-file-error.json"
            schema = self._write_schema(root)
            input_file.write_text("Alpha", encoding="utf-8")
            fake_result = types.SimpleNamespace(success=False, error=AppError(FILE_ERROR, "Failed to write file: /tmp/blocked.json"))

            with patch("extractor.cli.run_extraction", return_value=fake_result):
                code, out = self._run_cli(
                    [
                        "extract",
                        "run",
                        "--input",
                        str(input_file),
                        "--schema",
                        str(schema),
                        "--output",
                        str(output_file),
                    ]
                )

            self.assertEqual(code, 2)
            self.assertEqual(out, "ERROR FILE_ERROR Failed to write file: /tmp/blocked.json\n")
            payload = json.loads(Path(f"{output_file}.error.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["stage"], "internal")

    def test_batch_mode_does_not_write_error_artifact(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            input_dir = root / "inputs"
            output_dir = root / "outputs"
            input_dir.mkdir()
            output_dir.mkdir()
            (input_dir / "bad.txt").write_text("BADJSON", encoding="utf-8")
            schema = self._write_schema(root)

            code, out = self._run_cli(
                [
                    "extract",
                    "run",
                    "--input-dir",
                    str(input_dir),
                    "--schema",
                    str(schema),
                    "--output-dir",
                    str(output_dir),
                ]
            )
            self.assertEqual(code, 1)
            self.assertEqual(out, "total=1\nsuccess=0\ncontract_failure=1\nexecution_error=0\n")
            self.assertFalse((output_dir / "bad.json.error.json").exists())


if __name__ == "__main__":
    unittest.main()

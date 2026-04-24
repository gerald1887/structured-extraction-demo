import io
import json
import os
import sys
import tempfile
import types
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.modules.setdefault("openai", types.SimpleNamespace(OpenAI=object))

from extractor import cli
from extractor.errors import AppError, PROVIDER_ERROR
from extractor.input_validation import MAX_INPUT_BYTES


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


class GoodProvider:
    name = "test"

    def __init__(self, *args, **kwargs):
        pass

    def generate(self, prompt: str, model: str, temperature: float, max_tokens: int | None) -> str:
        return json.dumps({"name": "John", "age": 30, "city": "Bangalore"})


class ParseFailProvider:
    name = "test"

    def __init__(self, *args, **kwargs):
        pass

    def generate(self, prompt: str, model: str, temperature: float, max_tokens: int | None) -> str:
        return "not-json"


class SchemaMissingProvider:
    name = "test"

    def __init__(self, *args, **kwargs):
        pass

    def generate(self, prompt: str, model: str, temperature: float, max_tokens: int | None) -> str:
        return json.dumps({"name": "John", "city": "Bangalore"})


class SchemaTypeProvider:
    name = "test"

    def __init__(self, *args, **kwargs):
        pass

    def generate(self, prompt: str, model: str, temperature: float, max_tokens: int | None) -> str:
        return json.dumps({"name": "John", "age": "30", "city": "Bangalore"})


class ExecFailProvider:
    name = "test"

    def __init__(self, *args, **kwargs):
        pass

    def generate(self, prompt: str, model: str, temperature: float, max_tokens: int | None) -> str:
        raise AppError(PROVIDER_ERROR, "Provider request failed")


class FailIfCalledProvider:
    name = "test"

    def __init__(self, *args, **kwargs):
        pass

    def generate(self, prompt: str, model: str, temperature: float, max_tokens: int | None) -> str:
        raise AssertionError("provider should not be called")


class TestSnapshotCompareCli(unittest.TestCase):
    def _run_cli(self, argv: list[str], provider_class=GoodProvider):
        out = io.StringIO()
        with patch("extractor.cli.OpenAIProvider", provider_class), patch("sys.argv", argv), redirect_stdout(out):
            code = cli.main()
        return code, out.getvalue()

    def _setup_files(self, root: Path) -> tuple[Path, Path]:
        input_file = root / "input.txt"
        schema_file = root / "schema.json"
        input_file.write_text("John is 30 and lives in Bangalore", encoding="utf-8")
        schema_file.write_text(SCHEMA_TEXT, encoding="utf-8")
        return input_file, schema_file

    def test_snapshot_success_writes_exact_json(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            inp, schema = self._setup_files(root)
            snapshot = root / "golden.json"
            code, out = self._run_cli(
                ["extract", "snapshot", "--input", str(inp), "--schema", str(schema), "--output", str(snapshot)]
            )
            self.assertEqual(code, 0)
            self.assertEqual(out, "SUCCESS\n")
            data = json.loads(snapshot.read_text(encoding="utf-8"))
            self.assertEqual(data["name"], "John")
            self.assertEqual(data["age"], 30)
            self.assertEqual(data["city"], "Bangalore")

    def test_snapshot_json_parse_contract_failure_exit_1(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            inp, schema = self._setup_files(root)
            snapshot = root / "golden.json"
            code, out = self._run_cli(
                ["extract", "snapshot", "--input", str(inp), "--schema", str(schema), "--output", str(snapshot)],
                provider_class=ParseFailProvider,
            )
            self.assertEqual(code, 1)
            self.assertEqual(out, "ERROR JSON_PARSE_ERROR Invalid JSON returned by model\n")

    def test_snapshot_schema_validation_contract_failure_exit_1(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            inp, schema = self._setup_files(root)
            snapshot = root / "golden.json"
            code, out = self._run_cli(
                ["extract", "snapshot", "--input", str(inp), "--schema", str(schema), "--output", str(snapshot)],
                provider_class=SchemaMissingProvider,
            )
            self.assertEqual(code, 1)
            self.assertEqual(out, "ERROR SCHEMA_VALIDATION_ERROR Missing required field: age\n")

    def test_snapshot_execution_failure_exit_2(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            inp, schema = self._setup_files(root)
            snapshot = root / "golden.json"
            code, out = self._run_cli(
                ["extract", "snapshot", "--input", str(inp), "--schema", str(schema), "--output", str(snapshot)],
                provider_class=ExecFailProvider,
            )
            self.assertEqual(code, 2)
            self.assertEqual(out, "ERROR PROVIDER_ERROR Provider request failed\n")

    def test_snapshot_invalid_input_validation_failures_exit_2_and_no_output(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            schema = root / "schema.json"
            schema.write_text(SCHEMA_TEXT, encoding="utf-8")

            empty_input = root / "empty.txt"
            empty_input.write_text("", encoding="utf-8")
            oversized_input = root / "oversized.txt"
            oversized_input.write_bytes(b"a" * (MAX_INPUT_BYTES + 1))
            invalid_utf8_input = root / "invalid_utf8.txt"
            invalid_utf8_input.write_bytes(b"\xff\xfe\xfd")

            cases = [
                (empty_input, "ERROR FILE_ERROR Input is empty\n"),
                (oversized_input, f"ERROR FILE_ERROR Input exceeds max size limit: {MAX_INPUT_BYTES} bytes\n"),
                (invalid_utf8_input, "ERROR FILE_ERROR Input is not valid UTF-8\n"),
            ]
            for input_file, expected in cases:
                snapshot = root / f"{input_file.stem}.snapshot.json"
                code, out = self._run_cli(
                    [
                        "extract",
                        "snapshot",
                        "--input",
                        str(input_file),
                        "--schema",
                        str(schema),
                        "--output",
                        str(snapshot),
                    ],
                    provider_class=FailIfCalledProvider,
                )
                self.assertEqual(code, 2)
                self.assertEqual(out, expected)
                self.assertFalse(snapshot.exists())

    def test_compare_exact_match_exit_0(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            inp, schema = self._setup_files(root)
            snapshot = root / "golden.json"
            snapshot.write_text(json.dumps({"name": "John", "age": 30, "city": "Bangalore"}, sort_keys=True), encoding="utf-8")
            code, out = self._run_cli(
                ["extract", "compare", "--input", str(inp), "--schema", str(schema), "--snapshot", str(snapshot)]
            )
            self.assertEqual(code, 0)
            self.assertEqual(out, "MATCH\n")

    def test_compare_mismatch_prints_diff_exit_1(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            inp, schema = self._setup_files(root)
            snapshot = root / "golden.json"
            snapshot.write_text(json.dumps({"name": "Jane", "age": 30, "city": "Bangalore"}, sort_keys=True), encoding="utf-8")
            code, out = self._run_cli(
                ["extract", "compare", "--input", str(inp), "--schema", str(schema), "--snapshot", str(snapshot)]
            )
            self.assertEqual(code, 1)
            self.assertTrue(out.startswith("DIFF\n"))
            self.assertIn("DIFF mismatch /name expected=\"Jane\" actual=\"John\"", out)

    def test_compare_object_key_order_difference_only_exit_0(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            inp, schema = self._setup_files(root)
            snapshot = root / "golden.json"
            snapshot.write_text(
                '{"city":"Bangalore","age":30,"name":"John"}',
                encoding="utf-8",
            )
            code, out = self._run_cli(
                ["extract", "compare", "--input", str(inp), "--schema", str(schema), "--snapshot", str(snapshot)]
            )
            self.assertEqual(code, 0)
            self.assertEqual(out, "MATCH\n")

    def test_compare_array_order_difference_exit_1(self):
        class ArrayProvider:
            name = "test"

            def generate(self, prompt: str, model: str, temperature: float, max_tokens: int | None) -> str:
                return json.dumps({"name": "John", "age": 30, "city": "Bangalore", "arr": [1, 2]})

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            inp = root / "input.txt"
            schema = root / "schema.json"
            inp.write_text("x", encoding="utf-8")
            schema.write_text(
                json.dumps(
                    {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "age": {"type": "number"},
                            "city": {"type": "string"},
                            "arr": {"type": "array"},
                        },
                        "required": ["name", "age", "city", "arr"],
                    }
                ),
                encoding="utf-8",
            )
            snapshot = root / "golden.json"
            snapshot.write_text(json.dumps({"name": "John", "age": 30, "city": "Bangalore", "arr": [2, 1]}, sort_keys=True), encoding="utf-8")
            code, out = self._run_cli(
                ["extract", "compare", "--input", str(inp), "--schema", str(schema), "--snapshot", str(snapshot)],
                provider_class=ArrayProvider,
            )
            self.assertEqual(code, 1)
            self.assertIn("DIFF mismatch /arr/0", out)

    def test_compare_snapshot_missing_file_exit_2(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            inp, schema = self._setup_files(root)
            snapshot = root / "missing.json"
            code, out = self._run_cli(
                ["extract", "compare", "--input", str(inp), "--schema", str(schema), "--snapshot", str(snapshot)]
            )
            self.assertEqual(code, 2)
            self.assertEqual(out, f"ERROR FILE_ERROR Failed to read file: {snapshot}\n")

    def test_compare_snapshot_invalid_json_exit_2(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            inp, schema = self._setup_files(root)
            snapshot = root / "golden.json"
            snapshot.write_text("{invalid", encoding="utf-8")
            code, out = self._run_cli(
                ["extract", "compare", "--input", str(inp), "--schema", str(schema), "--snapshot", str(snapshot)]
            )
            self.assertEqual(code, 2)
            self.assertEqual(out, "ERROR INTERNAL_ERROR Internal error\n")

    def test_compare_invalid_input_validation_failures_exit_2_and_provider_not_called(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            schema = root / "schema.json"
            schema.write_text(SCHEMA_TEXT, encoding="utf-8")
            snapshot = root / "golden.json"
            snapshot.write_text(json.dumps({"name": "John", "age": 30, "city": "Bangalore"}, sort_keys=True), encoding="utf-8")

            empty_input = root / "empty.txt"
            empty_input.write_text("", encoding="utf-8")
            oversized_input = root / "oversized.txt"
            oversized_input.write_bytes(b"a" * (MAX_INPUT_BYTES + 1))
            invalid_utf8_input = root / "invalid_utf8.txt"
            invalid_utf8_input.write_bytes(b"\xff\xfe\xfd")

            cases = [
                (empty_input, "ERROR FILE_ERROR Input is empty\n"),
                (oversized_input, f"ERROR FILE_ERROR Input exceeds max size limit: {MAX_INPUT_BYTES} bytes\n"),
                (invalid_utf8_input, "ERROR FILE_ERROR Input is not valid UTF-8\n"),
            ]
            for input_file, expected in cases:
                code, out = self._run_cli(
                    [
                        "extract",
                        "compare",
                        "--input",
                        str(input_file),
                        "--schema",
                        str(schema),
                        "--snapshot",
                        str(snapshot),
                    ],
                    provider_class=FailIfCalledProvider,
                )
                self.assertEqual(code, 2)
                self.assertEqual(out, expected)

    def test_compare_fresh_extraction_contract_failure_exit_1(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            inp, schema = self._setup_files(root)
            snapshot = root / "golden.json"
            snapshot.write_text(json.dumps({"name": "John", "age": 30, "city": "Bangalore"}, sort_keys=True), encoding="utf-8")
            code, out = self._run_cli(
                ["extract", "compare", "--input", str(inp), "--schema", str(schema), "--snapshot", str(snapshot)],
                provider_class=SchemaTypeProvider,
            )
            self.assertEqual(code, 1)
            self.assertEqual(out, "ERROR SCHEMA_VALIDATION_ERROR Schema validation failed\n")

    def test_provider_openai_supported_and_unsupported_provider_exit_2(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            inp, schema = self._setup_files(root)
            snapshot = root / "golden.json"
            code_openai, _ = self._run_cli(
                [
                    "extract",
                    "snapshot",
                    "--input",
                    str(inp),
                    "--schema",
                    str(schema),
                    "--output",
                    str(snapshot),
                    "--provider",
                    "openai",
                ]
            )
            code_bad, out_bad = self._run_cli(
                [
                    "extract",
                    "compare",
                    "--input",
                    str(inp),
                    "--schema",
                    str(schema),
                    "--snapshot",
                    str(snapshot),
                    "--provider",
                    "other",
                ]
            )
            self.assertEqual(code_openai, 0)
            self.assertEqual(code_bad, 2)
            self.assertEqual(out_bad, "ERROR FILE_ERROR Failed to read file: unsupported provider: other\n")

    def test_snapshot_simulate_provider_timeout_exit_2(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            inp, schema = self._setup_files(root)
            snapshot = root / "golden.json"
            out = io.StringIO()
            with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=False), patch("sys.argv", [
                "extract",
                "snapshot",
                "--input",
                str(inp),
                "--schema",
                str(schema),
                "--output",
                str(snapshot),
                "--simulate-provider-error",
                "timeout",
            ]), redirect_stdout(out):
                code = cli.main()
            self.assertEqual(code, 2)
            self.assertEqual(out.getvalue(), "ERROR PROVIDER_ERROR Provider timeout (simulated)\n")

    def test_compare_simulate_provider_rate_limit_exit_2(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            inp, schema = self._setup_files(root)
            snapshot = root / "golden.json"
            snapshot.write_text(json.dumps({"name": "John", "age": 30, "city": "Bangalore"}, sort_keys=True), encoding="utf-8")
            out = io.StringIO()
            with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=False), patch("sys.argv", [
                "extract",
                "compare",
                "--input",
                str(inp),
                "--schema",
                str(schema),
                "--snapshot",
                str(snapshot),
                "--simulate-provider-error",
                "rate_limit",
            ]), redirect_stdout(out):
                code = cli.main()
            self.assertEqual(code, 2)
            self.assertEqual(out.getvalue(), "ERROR PROVIDER_ERROR Provider rate limit (simulated)\n")


if __name__ == "__main__":
    unittest.main()

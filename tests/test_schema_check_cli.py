import io
import json
import sys
import tempfile
import types
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.modules.setdefault("openai", types.SimpleNamespace(OpenAI=object))

from extractor import cli


class TestSchemaCheckCli(unittest.TestCase):
    def _run_cli(self, argv: list[str]):
        out = io.StringIO()
        with patch("sys.argv", argv), redirect_stdout(out):
            code = cli.main()
        return code, out.getvalue()

    def _write_schema(self, path: Path, schema: dict) -> None:
        path.write_text(json.dumps(schema), encoding="utf-8")

    def test_schema_check_single_file_compatible_exit_0(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            artifact = root / "out.json"
            schema = root / "new_schema.json"
            artifact.write_text(json.dumps({"name": "John", "age": 30}), encoding="utf-8")
            self._write_schema(
                schema,
                {
                    "type": "object",
                    "properties": {"name": {"type": "string"}, "age": {"type": "number"}},
                    "required": ["name", "age"],
                },
            )
            code, out = self._run_cli(
                ["extract", "schema-check", "--input", str(artifact), "--new-schema", str(schema)]
            )
            self.assertEqual(code, 0)
            self.assertEqual(
                out,
                "SCHEMA CHECK out.json COMPATIBLE\nSCHEMA CHECK SUMMARY total=1 compatible=1 breaking_change=0\n",
            )

    def test_schema_check_single_file_breaking_change_exit_1(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            artifact = root / "out.json"
            schema = root / "new_schema.json"
            artifact.write_text(json.dumps({"name": "John"}), encoding="utf-8")
            self._write_schema(
                schema,
                {
                    "type": "object",
                    "properties": {"name": {"type": "string"}, "age": {"type": "number"}},
                    "required": ["name", "age"],
                },
            )
            code, out = self._run_cli(
                ["extract", "schema-check", "--input", str(artifact), "--new-schema", str(schema)]
            )
            self.assertEqual(code, 1)
            self.assertEqual(
                out,
                "SCHEMA CHECK out.json BREAKING_CHANGE\nSCHEMA CHECK SUMMARY total=1 compatible=0 breaking_change=1\n",
            )

    def test_schema_check_directory_sorted_and_summary(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            artifacts = root / "artifacts"
            artifacts.mkdir()
            schema = root / "new_schema.json"
            (artifacts / "b.json").write_text(json.dumps({"name": "John"}), encoding="utf-8")
            (artifacts / "a.json").write_text(json.dumps({"name": "John", "age": 30}), encoding="utf-8")
            self._write_schema(
                schema,
                {
                    "type": "object",
                    "properties": {"name": {"type": "string"}, "age": {"type": "number"}},
                    "required": ["name", "age"],
                },
            )
            code, out = self._run_cli(
                ["extract", "schema-check", "--input", str(artifacts), "--new-schema", str(schema)]
            )
            self.assertEqual(code, 1)
            self.assertEqual(
                out,
                "SCHEMA CHECK a.json COMPATIBLE\n"
                "SCHEMA CHECK b.json BREAKING_CHANGE\n"
                "SCHEMA CHECK SUMMARY total=2 compatible=1 breaking_change=1\n",
            )

    def test_schema_check_invalid_artifact_json_execution_error_exit_2(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            artifact = root / "out.json"
            schema = root / "new_schema.json"
            artifact.write_text("{invalid", encoding="utf-8")
            self._write_schema(schema, {"type": "object"})
            code, out = self._run_cli(
                ["extract", "schema-check", "--input", str(artifact), "--new-schema", str(schema)]
            )
            self.assertEqual(code, 2)
            self.assertEqual(out, "ERROR JSON_PARSE_ERROR Invalid JSON returned by model\n")

    def test_schema_check_invalid_schema_json_execution_error_exit_2(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            artifact = root / "out.json"
            schema = root / "new_schema.json"
            artifact.write_text(json.dumps({"name": "John"}), encoding="utf-8")
            schema.write_text("{invalid", encoding="utf-8")
            code, out = self._run_cli(
                ["extract", "schema-check", "--input", str(artifact), "--new-schema", str(schema)]
            )
            self.assertEqual(code, 2)
            self.assertEqual(out, "ERROR INTERNAL_ERROR Internal error\n")

    def test_schema_check_directory_invalid_json_no_partial_success(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            artifacts = root / "artifacts"
            artifacts.mkdir()
            schema = root / "new_schema.json"
            (artifacts / "a.json").write_text(json.dumps({"name": "John"}), encoding="utf-8")
            (artifacts / "b.json").write_text("{invalid", encoding="utf-8")
            self._write_schema(schema, {"type": "object"})
            code, out = self._run_cli(
                ["extract", "schema-check", "--input", str(artifacts), "--new-schema", str(schema)]
            )
            self.assertEqual(code, 2)
            self.assertEqual(out, "ERROR JSON_PARSE_ERROR Invalid JSON returned by model\n")

    def test_schema_check_report_write_failure_prints_only_error(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            artifact = root / "out.json"
            schema = root / "new_schema.json"
            report = root / "missing" / "report.json"
            artifact.write_text(json.dumps({"name": "John"}), encoding="utf-8")
            self._write_schema(schema, {"type": "object"})
            code, out = self._run_cli(
                [
                    "extract",
                    "schema-check",
                    "--input",
                    str(artifact),
                    "--new-schema",
                    str(schema),
                    "--output",
                    str(report),
                ]
            )
            self.assertEqual(code, 2)
            self.assertEqual(out, f"ERROR FILE_ERROR Failed to write file: {report}\n")

    def test_schema_check_optional_report_written_deterministically(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            artifact = root / "out.json"
            schema = root / "new_schema.json"
            report = root / "report.json"
            artifact.write_text(json.dumps({"name": "John"}), encoding="utf-8")
            self._write_schema(
                schema,
                {
                    "type": "object",
                    "properties": {"name": {"type": "string"}, "age": {"type": "number"}},
                    "required": ["name", "age"],
                },
            )
            code, out = self._run_cli(
                [
                    "extract",
                    "schema-check",
                    "--input",
                    str(artifact),
                    "--new-schema",
                    str(schema),
                    "--output",
                    str(report),
                ]
            )
            self.assertEqual(code, 1)
            self.assertEqual(
                out,
                "SCHEMA CHECK out.json BREAKING_CHANGE\nSCHEMA CHECK SUMMARY total=1 compatible=0 breaking_change=1\n",
            )
            expected = {
                "items": [{"path": "out.json", "classification": "BREAKING_CHANGE"}],
                "summary": {"total": 1, "compatible": 0, "breaking_change": 1},
            }
            self.assertEqual(json.loads(report.read_text(encoding="utf-8")), expected)

    def test_schema_check_ignores_meta_for_strict_schema(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            artifact = root / "strict_result.json"
            schema = root / "new_schema.json"
            artifact.write_text(
                json.dumps({"name": "John", "age": 30, "city": "Bangalore", "_meta": {"x": 1}}),
                encoding="utf-8",
            )
            self._write_schema(
                schema,
                {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "age": {"type": "number"},
                        "city": {"type": "string"},
                    },
                    "required": ["name", "age", "city"],
                    "additionalProperties": False,
                },
            )
            code, out = self._run_cli(
                ["extract", "schema-check", "--input", str(artifact), "--new-schema", str(schema)]
            )
            self.assertEqual(code, 0)
            self.assertEqual(
                out,
                "SCHEMA CHECK strict_result.json COMPATIBLE\nSCHEMA CHECK SUMMARY total=1 compatible=1 breaking_change=0\n",
            )


if __name__ == "__main__":
    unittest.main()

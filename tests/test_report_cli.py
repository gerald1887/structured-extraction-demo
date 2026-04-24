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
from extractor.errors import AppError, FILE_ERROR, INTERNAL_ERROR, PROVIDER_ERROR


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


class ErrProvider:
    name = "test"

    def __init__(self, *args, **kwargs):
        pass

    def generate(self, prompt: str, model: str, temperature: float, max_tokens: int | None) -> str:
        raise AppError(PROVIDER_ERROR, "Provider request failed")


class TestReportCli(unittest.TestCase):
    def _run_cli(self, argv: list[str], provider_class=GoodProvider):
        out = io.StringIO()
        with patch("extractor.cli.OpenAIProvider", provider_class), patch("sys.argv", argv), redirect_stdout(out):
            code = cli.main()
        return code, out.getvalue()

    def _write_schema(self, root: Path) -> Path:
        path = root / "schema.json"
        path.write_text(SCHEMA_TEXT, encoding="utf-8")
        return path

    def _assert_canonical(self, path: Path) -> dict:
        text = path.read_text(encoding="utf-8")
        data = json.loads(text)
        self.assertEqual(text, json.dumps(data, indent=2, sort_keys=True) + "\n")
        return data

    def test_no_report_file_when_report_absent(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            inp = root / "in.txt"
            out_json = root / "out.json"
            report = root / "report.json"
            schema = self._write_schema(root)
            inp.write_text("x", encoding="utf-8")
            code, out = self._run_cli(
                ["extract", "run", "--input", str(inp), "--schema", str(schema), "--output", str(out_json)]
            )
            self.assertEqual(code, 0)
            self.assertEqual(out, "SUCCESS\n")
            self.assertFalse(report.exists())

    def test_run_success_report(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            inp = root / "in.txt"
            out_json = root / "out.json"
            report = root / "report.json"
            schema = self._write_schema(root)
            inp.write_text("x", encoding="utf-8")
            code, out = self._run_cli(
                [
                    "extract",
                    "run",
                    "--input",
                    str(inp),
                    "--schema",
                    str(schema),
                    "--output",
                    str(out_json),
                    "--report",
                    str(report),
                ]
            )
            self.assertEqual(code, 0)
            self.assertEqual(out, "SUCCESS\n")
            payload = self._assert_canonical(report)
            self.assertEqual(payload["command"], "run")
            self.assertEqual(payload["summary"]["success_count"], 1)
            self.assertEqual(payload["cases"][0]["status"], "SUCCESS")
            self.assertIsInstance(payload["cases"][0]["prompt_hash"], str)

    def test_run_error_report(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            inp = root / "in.txt"
            out_json = root / "out.json"
            report = root / "report.json"
            schema = self._write_schema(root)
            inp.write_text("x", encoding="utf-8")
            code, out = self._run_cli(
                [
                    "extract",
                    "run",
                    "--input",
                    str(inp),
                    "--schema",
                    str(schema),
                    "--output",
                    str(out_json),
                    "--report",
                    str(report),
                ],
                provider_class=ErrProvider,
            )
            self.assertEqual(code, 2)
            self.assertEqual(out, "ERROR PROVIDER_ERROR Provider request failed\n")
            payload = self._assert_canonical(report)
            self.assertEqual(payload["summary"]["error_count"], 1)
            self.assertEqual(payload["cases"][0]["status"], "ERROR")
            self.assertEqual(payload["cases"][0]["error_type"], "PROVIDER_ERROR")
            self.assertIsInstance(payload["cases"][0]["prompt_hash"], str)

    def test_run_expected_prompt_hash_mismatch_error_report(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            inp = root / "in.txt"
            out_json = root / "out.json"
            report = root / "report.json"
            schema = self._write_schema(root)
            inp.write_text("x", encoding="utf-8")
            code, out = self._run_cli(
                [
                    "extract",
                    "run",
                    "--input",
                    str(inp),
                    "--schema",
                    str(schema),
                    "--output",
                    str(out_json),
                    "--expected-prompt-hash",
                    "wrong-hash",
                    "--report",
                    str(report),
                ]
            )
            self.assertEqual(code, 2)
            self.assertEqual(out, "ERROR INTERNAL_ERROR Prompt hash mismatch\n")
            payload = self._assert_canonical(report)
            self.assertEqual(payload["cases"][0]["status"], "ERROR")
            self.assertEqual(payload["cases"][0]["error_type"], INTERNAL_ERROR)
            self.assertIsInstance(payload["cases"][0]["prompt_hash"], str)

    def test_snapshot_success_and_error_report(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            inp = root / "in.txt"
            schema = self._write_schema(root)
            snap = root / "snap.json"
            report_ok = root / "report_ok.json"
            report_err = root / "report_err.json"
            inp.write_text("x", encoding="utf-8")
            code_ok, out_ok = self._run_cli(
                [
                    "extract",
                    "snapshot",
                    "--input",
                    str(inp),
                    "--schema",
                    str(schema),
                    "--output",
                    str(snap),
                    "--report",
                    str(report_ok),
                ]
            )
            self.assertEqual(code_ok, 0)
            self.assertEqual(out_ok, "SUCCESS\n")
            payload_ok = self._assert_canonical(report_ok)
            self.assertEqual(payload_ok["command"], "snapshot")
            self.assertEqual(payload_ok["cases"][0]["status"], "SUCCESS")

            code_err, out_err = self._run_cli(
                [
                    "extract",
                    "snapshot",
                    "--input",
                    str(inp),
                    "--schema",
                    str(schema),
                    "--output",
                    str(snap),
                    "--report",
                    str(report_err),
                ],
                provider_class=ErrProvider,
            )
            self.assertEqual(code_err, 2)
            self.assertEqual(out_err, "ERROR PROVIDER_ERROR Provider request failed\n")
            payload_err = self._assert_canonical(report_err)
            self.assertEqual(payload_err["cases"][0]["status"], "ERROR")
            self.assertEqual(payload_err["cases"][0]["error_type"], "PROVIDER_ERROR")

    def test_diff_same_diff_and_error_reports(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            expected = root / "expected.json"
            actual = root / "actual.json"
            report = root / "report.json"
            expected.write_text('{"a":1}', encoding="utf-8")
            actual.write_text('{"a":1}', encoding="utf-8")
            code_same, out_same = self._run_cli(
                [
                    "extract",
                    "diff",
                    "--expected",
                    str(expected),
                    "--actual",
                    str(actual),
                    "--report",
                    str(report),
                ]
            )
            self.assertEqual(code_same, 0)
            self.assertEqual(json.loads(out_same)["status"], "PASS")
            payload_same = self._assert_canonical(report)
            self.assertEqual(payload_same["cases"][0]["status"], "SUCCESS")

            actual.write_text('{"a":2}', encoding="utf-8")
            code_diff, out_diff = self._run_cli(
                [
                    "extract",
                    "diff",
                    "--expected",
                    str(expected),
                    "--actual",
                    str(actual),
                    "--report",
                    str(report),
                ]
            )
            self.assertEqual(code_diff, 1)
            self.assertEqual(json.loads(out_diff)["status"], "DIFF")
            payload_diff = self._assert_canonical(report)
            self.assertEqual(payload_diff["cases"][0]["status"], "DIFF")

            expected.write_text("{invalid", encoding="utf-8")
            code_err, out_err = self._run_cli(
                [
                    "extract",
                    "diff",
                    "--expected",
                    str(expected),
                    "--actual",
                    str(actual),
                    "--report",
                    str(report),
                ]
            )
            self.assertEqual(code_err, 2)
            self.assertEqual(json.loads(out_err)["status"], "ERROR")
            payload_err = self._assert_canonical(report)
            self.assertEqual(payload_err["cases"][0]["status"], "ERROR")
            self.assertEqual(payload_err["cases"][0]["error_type"], "JSON_PARSE_ERROR")

    def test_report_write_failure_exits_2(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            inp = root / "in.txt"
            out_json = root / "out.json"
            report = root / "report.json"
            schema = self._write_schema(root)
            inp.write_text("x", encoding="utf-8")
            with patch("extractor.cli.write_report_json", side_effect=AppError(FILE_ERROR, "Failed to write file: bad")):
                code, out = self._run_cli(
                    [
                        "extract",
                        "run",
                        "--input",
                        str(inp),
                        "--schema",
                        str(schema),
                        "--output",
                        str(out_json),
                        "--report",
                        str(report),
                    ]
                )
            self.assertEqual(code, 2)
            self.assertEqual(out, "ERROR FILE_ERROR Failed to write file: bad\n")


if __name__ == "__main__":
    unittest.main()

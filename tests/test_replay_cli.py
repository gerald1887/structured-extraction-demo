import io
import json
import sys
import tempfile
import types
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.modules.setdefault("openai", types.SimpleNamespace(OpenAI=object))

from extractor import cli


class TestReplayCli(unittest.TestCase):
    def _run_cli(self, argv: list[str]) -> tuple[int, str, str]:
        out = io.StringIO()
        err = io.StringIO()
        with patch("sys.argv", argv), redirect_stdout(out), redirect_stderr(err):
            code = cli.main()
        return code, out.getvalue(), err.getvalue()

    def test_replay_pass_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            p = root / "artifact.json"
            p.write_text(
                json.dumps(
                    {"status": "PASS", "exit_code": 0, "stdout": "PASS: Contract satisfied\n", "stderr": ""},
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            code, out, err = self._run_cli(["extract", "replay", "--input", str(p)])
            self.assertEqual(code, 0)
            self.assertEqual(out, "PASS: Contract satisfied\n")
            self.assertEqual(err, "")

    def test_replay_fail_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            p = root / "artifact.json"
            p.write_text(
                json.dumps(
                    {"status": "FAIL", "exit_code": 1, "stdout": "FAIL: Contract violated\n", "stderr": ""},
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            code, out, err = self._run_cli(["extract", "replay", "--input", str(p)])
            self.assertEqual(code, 1)
            self.assertEqual(out, "FAIL: Contract violated\n")
            self.assertEqual(err, "")

    def test_replay_error_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            p = root / "artifact.json"
            p.write_text(
                json.dumps(
                    {"status": "ERROR", "exit_code": 2, "stdout": "", "stderr": "some error\n"},
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            code, out, err = self._run_cli(["extract", "replay", "--input", str(p)])
            self.assertEqual(code, 2)
            self.assertEqual(out, "")
            self.assertEqual(err, "some error\n")

    def test_replay_file_error(self) -> None:
        code, out, err = self._run_cli(["extract", "replay", "--input", "/tmp/does-not-exist-artifact.json"])
        self.assertEqual(code, 2)
        self.assertTrue(out.startswith("ERROR FILE_ERROR Failed to read file:"))
        self.assertEqual(err, "")

    def test_replay_json_parse_error(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            p = root / "artifact.json"
            p.write_text("not-json", encoding="utf-8")
            code, out, err = self._run_cli(["extract", "replay", "--input", str(p)])
            self.assertEqual(code, 2)
            self.assertEqual(out, f"ERROR JSON_PARSE_ERROR Invalid JSON file: {p}\n")
            self.assertEqual(err, "")

    def test_replay_schema_validation_error(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            p = root / "artifact.json"
            p.write_text(
                json.dumps({"status": "PASS", "exit_code": "0", "stdout": "x", "stderr": ""}, indent=2, sort_keys=True)
                + "\n",
                encoding="utf-8",
            )
            code, out, err = self._run_cli(["extract", "replay", "--input", str(p)])
            self.assertEqual(code, 2)
            self.assertEqual(out, "ERROR SCHEMA_VALIDATION_ERROR Replay artifact exit_code must be int\n")
            self.assertEqual(err, "")

    def test_replay_schema_validation_error_exit_code_true(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            p = root / "artifact.json"
            p.write_text(
                json.dumps({"status": "PASS", "exit_code": True, "stdout": "x", "stderr": ""}, indent=2, sort_keys=True)
                + "\n",
                encoding="utf-8",
            )
            code, out, err = self._run_cli(["extract", "replay", "--input", str(p)])
            self.assertEqual(code, 2)
            self.assertEqual(out, "ERROR SCHEMA_VALIDATION_ERROR Replay artifact exit_code must be int\n")
            self.assertEqual(err, "")

    def test_replay_schema_validation_error_exit_code_false(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            p = root / "artifact.json"
            p.write_text(
                json.dumps({"status": "PASS", "exit_code": False, "stdout": "x", "stderr": ""}, indent=2, sort_keys=True)
                + "\n",
                encoding="utf-8",
            )
            code, out, err = self._run_cli(["extract", "replay", "--input", str(p)])
            self.assertEqual(code, 2)
            self.assertEqual(out, "ERROR SCHEMA_VALIDATION_ERROR Replay artifact exit_code must be int\n")
            self.assertEqual(err, "")

    def test_replay_schema_validation_error_exit_code_negative(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            p = root / "artifact.json"
            p.write_text(
                json.dumps({"status": "PASS", "exit_code": -1, "stdout": "x", "stderr": ""}, indent=2, sort_keys=True)
                + "\n",
                encoding="utf-8",
            )
            code, out, err = self._run_cli(["extract", "replay", "--input", str(p)])
            self.assertEqual(code, 2)
            self.assertEqual(out, "ERROR SCHEMA_VALIDATION_ERROR Replay artifact exit_code must be in range 0-255\n")
            self.assertEqual(err, "")

    def test_replay_schema_validation_error_exit_code_too_large(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            p = root / "artifact.json"
            p.write_text(
                json.dumps({"status": "PASS", "exit_code": 256, "stdout": "x", "stderr": ""}, indent=2, sort_keys=True)
                + "\n",
                encoding="utf-8",
            )
            code, out, err = self._run_cli(["extract", "replay", "--input", str(p)])
            self.assertEqual(code, 2)
            self.assertEqual(out, "ERROR SCHEMA_VALIDATION_ERROR Replay artifact exit_code must be in range 0-255\n")
            self.assertEqual(err, "")


if __name__ == "__main__":
    unittest.main()

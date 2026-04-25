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


class TestDiffArtifactsCli(unittest.TestCase):
    def _run_cli(self, argv: list[str]) -> tuple[int, str]:
        out = io.StringIO()
        with patch("sys.argv", argv), redirect_stdout(out):
            code = cli.main()
        return code, out.getvalue()

    @staticmethod
    def _write_json(path: Path, value: object) -> None:
        path.write_text(json.dumps(value), encoding="utf-8")

    def test_diff_artifacts_match(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            expected = root / "expected.json"
            actual = root / "actual.json"
            self._write_json(expected, {"status": "PASS", "exit_code": 0, "stdout": "ok\n", "stderr": ""})
            self._write_json(actual, {"stdout": "ok\n", "stderr": "", "exit_code": 0, "status": "PASS"})
            code, out = self._run_cli(["extract", "diff-artifacts", "--expected", str(expected), "--actual", str(actual)])
            self.assertEqual(code, 0)
            self.assertEqual(out, "MATCH\n")

    def test_diff_artifacts_diff(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            expected = root / "expected.json"
            actual = root / "actual.json"
            self._write_json(expected, {"status": "PASS", "exit_code": 0, "stdout": "ok\n", "stderr": ""})
            self._write_json(actual, {"status": "FAIL", "exit_code": 1, "stdout": "bad\n", "stderr": ""})
            code, out = self._run_cli(["extract", "diff-artifacts", "--expected", str(expected), "--actual", str(actual)])
            self.assertEqual(code, 1)
            self.assertEqual(out, "DIFF\n")

    def test_diff_artifacts_missing_expected_file(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            expected = root / "missing.json"
            actual = root / "actual.json"
            self._write_json(actual, {"status": "PASS", "exit_code": 0, "stdout": "ok\n", "stderr": ""})
            code, out = self._run_cli(["extract", "diff-artifacts", "--expected", str(expected), "--actual", str(actual)])
            self.assertEqual(code, 2)
            payload = json.loads(out)
            self.assertEqual(payload["status"], "ERROR")
            self.assertEqual(payload["error_type"], "FILE_ERROR")

    def test_diff_artifacts_invalid_json(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            expected = root / "expected.json"
            actual = root / "actual.json"
            self._write_json(expected, {"status": "PASS", "exit_code": 0, "stdout": "ok\n", "stderr": ""})
            actual.write_text("{not-json", encoding="utf-8")
            code, out = self._run_cli(["extract", "diff-artifacts", "--expected", str(expected), "--actual", str(actual)])
            self.assertEqual(code, 2)
            payload = json.loads(out)
            self.assertEqual(payload["status"], "ERROR")
            self.assertEqual(payload["error_type"], "JSON_PARSE_ERROR")

    def test_diff_artifacts_bool_vs_int_is_diff(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            expected = root / "expected.json"
            actual = root / "actual.json"
            self._write_json(expected, {"flag": True})
            self._write_json(actual, {"flag": 1})
            code, out = self._run_cli(["extract", "diff-artifacts", "--expected", str(expected), "--actual", str(actual)])
            self.assertEqual(code, 1)
            self.assertEqual(out, "DIFF\n")


if __name__ == "__main__":
    unittest.main()

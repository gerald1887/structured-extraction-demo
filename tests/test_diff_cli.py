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


class TestDiffCli(unittest.TestCase):
    def _run_cli(self, argv: list[str]):
        out = io.StringIO()
        with patch("sys.argv", argv), redirect_stdout(out):
            code = cli.main()
        return code, out.getvalue()

    def _write_json(self, path: Path, value: object) -> None:
        path.write_text(json.dumps(value), encoding="utf-8")

    def test_diff_pass_exits_0_and_prints_canonical_json(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            expected = root / "expected.json"
            actual = root / "actual.json"
            expected.write_text('{"a":1,"b":{"x":2,"y":3}}', encoding="utf-8")
            actual.write_text('{"b":{"y":3,"x":2},"a":1}', encoding="utf-8")
            code, out = self._run_cli(["extract", "diff", "--expected", str(expected), "--actual", str(actual)])
            self.assertEqual(code, 0)
            self.assertEqual(out, "{\n  \"diffs\": [],\n  \"status\": \"PASS\"\n}\n")

    def test_object_key_reorder_still_pass(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            expected = root / "e.json"
            actual = root / "a.json"
            expected.write_text('{"city":"Bangalore","age":30,"name":"John"}', encoding="utf-8")
            actual.write_text('{"name":"John","age":30,"city":"Bangalore"}', encoding="utf-8")
            code, out = self._run_cli(["extract", "diff", "--expected", str(expected), "--actual", str(actual)])
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(out), {"status": "PASS", "diffs": []})

    def test_missing_field_exits_1(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            expected = root / "e.json"
            actual = root / "a.json"
            self._write_json(expected, {"name": "John", "age": 30})
            self._write_json(actual, {"name": "John"})
            code, out = self._run_cli(["extract", "diff", "--expected", str(expected), "--actual", str(actual)])
            self.assertEqual(code, 1)
            payload = json.loads(out)
            self.assertEqual(payload["status"], "DIFF")
            self.assertEqual(payload["diffs"][0]["type"], "missing")
            self.assertEqual(payload["diffs"][0]["path"], "/age")
            self.assertEqual(payload["diffs"][0]["expected_value"], 30)
            self.assertNotIn("actual_value", payload["diffs"][0])

    def test_directionality_missing_expected_key_not_in_actual(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            expected = root / "expected.json"
            actual = root / "actual.json"
            self._write_json(expected, {"a": 1, "b": 2})
            self._write_json(actual, {"a": 1})
            code, out = self._run_cli(["extract", "diff", "--expected", str(expected), "--actual", str(actual)])
            self.assertEqual(code, 1)
            payload = json.loads(out)
            self.assertEqual(payload["status"], "DIFF")
            self.assertEqual(payload["diffs"][0]["type"], "missing")
            self.assertEqual(payload["diffs"][0]["path"], "/b")
            self.assertEqual(payload["diffs"][0]["expected_value"], 2)
            self.assertNotIn("actual_value", payload["diffs"][0])

    def test_extra_field_exits_1(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            expected = root / "e.json"
            actual = root / "a.json"
            self._write_json(expected, {"name": "John"})
            self._write_json(actual, {"name": "John", "age": 30})
            code, out = self._run_cli(["extract", "diff", "--expected", str(expected), "--actual", str(actual)])
            self.assertEqual(code, 1)
            payload = json.loads(out)
            self.assertEqual(payload["diffs"][0]["type"], "extra")
            self.assertEqual(payload["diffs"][0]["path"], "/age")
            self.assertEqual(payload["diffs"][0]["actual_value"], 30)
            self.assertNotIn("expected_value", payload["diffs"][0])

    def test_directionality_extra_actual_key_not_in_expected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            expected = root / "expected.json"
            actual = root / "actual.json"
            self._write_json(expected, {"a": 1})
            self._write_json(actual, {"a": 1, "b": 2})
            code, out = self._run_cli(["extract", "diff", "--expected", str(expected), "--actual", str(actual)])
            self.assertEqual(code, 1)
            payload = json.loads(out)
            self.assertEqual(payload["status"], "DIFF")
            self.assertEqual(payload["diffs"][0]["type"], "extra")
            self.assertEqual(payload["diffs"][0]["path"], "/b")
            self.assertEqual(payload["diffs"][0]["actual_value"], 2)
            self.assertNotIn("expected_value", payload["diffs"][0])

    def test_mismatch_exits_1(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            expected = root / "e.json"
            actual = root / "a.json"
            self._write_json(expected, {"age": 30})
            self._write_json(actual, {"age": 31})
            code, out = self._run_cli(["extract", "diff", "--expected", str(expected), "--actual", str(actual)])
            self.assertEqual(code, 1)
            payload = json.loads(out)
            self.assertEqual(payload["diffs"][0]["type"], "mismatch")
            self.assertEqual(payload["diffs"][0]["path"], "/age")
            self.assertEqual(payload["diffs"][0]["expected_value"], 30)
            self.assertEqual(payload["diffs"][0]["actual_value"], 31)

    def test_nested_object_path_uses_json_pointer(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            expected = root / "e.json"
            actual = root / "a.json"
            self._write_json(expected, {"a": {"b": 1}})
            self._write_json(actual, {"a": {"b": 2}})
            code, out = self._run_cli(["extract", "diff", "--expected", str(expected), "--actual", str(actual)])
            self.assertEqual(code, 1)
            self.assertEqual(json.loads(out)["diffs"][0]["path"], "/a/b")

    def test_array_positional_mismatch_uses_index_pointer(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            expected = root / "e.json"
            actual = root / "a.json"
            self._write_json(expected, {"arr": [1, 2]})
            self._write_json(actual, {"arr": [2, 1]})
            code, out = self._run_cli(["extract", "diff", "--expected", str(expected), "--actual", str(actual)])
            self.assertEqual(code, 1)
            self.assertEqual(json.loads(out)["diffs"][0]["path"], "/arr/0")

    def test_invalid_expected_json_exits_2_with_json_parse_error(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            expected = root / "e.json"
            actual = root / "a.json"
            expected.write_text("{invalid", encoding="utf-8")
            self._write_json(actual, {"x": 1})
            code, out = self._run_cli(["extract", "diff", "--expected", str(expected), "--actual", str(actual)])
            self.assertEqual(code, 2)
            payload = json.loads(out)
            self.assertEqual(payload["status"], "ERROR")
            self.assertEqual(payload["error_type"], "JSON_PARSE_ERROR")

    def test_invalid_actual_json_exits_2_with_json_parse_error(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            expected = root / "e.json"
            actual = root / "a.json"
            self._write_json(expected, {"x": 1})
            actual.write_text("{invalid", encoding="utf-8")
            code, out = self._run_cli(["extract", "diff", "--expected", str(expected), "--actual", str(actual)])
            self.assertEqual(code, 2)
            payload = json.loads(out)
            self.assertEqual(payload["status"], "ERROR")
            self.assertEqual(payload["error_type"], "JSON_PARSE_ERROR")

    def test_missing_expected_file_exits_2_with_file_error(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            expected = root / "missing.json"
            actual = root / "a.json"
            self._write_json(actual, {"x": 1})
            code, out = self._run_cli(["extract", "diff", "--expected", str(expected), "--actual", str(actual)])
            self.assertEqual(code, 2)
            payload = json.loads(out)
            self.assertEqual(payload["status"], "ERROR")
            self.assertEqual(payload["error_type"], "FILE_ERROR")

    def test_missing_actual_file_exits_2_with_file_error(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            expected = root / "e.json"
            actual = root / "missing.json"
            self._write_json(expected, {"x": 1})
            code, out = self._run_cli(["extract", "diff", "--expected", str(expected), "--actual", str(actual)])
            self.assertEqual(code, 2)
            payload = json.loads(out)
            self.assertEqual(payload["status"], "ERROR")
            self.assertEqual(payload["error_type"], "FILE_ERROR")


if __name__ == "__main__":
    unittest.main()

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

try:
    import sentinel  # noqa: F401

    _SENTINEL_AVAILABLE = True
except ImportError:
    _SENTINEL_AVAILABLE = False

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


@unittest.skipUnless(_SENTINEL_AVAILABLE, "sentinel package not installed (pip install -e /path/to/sentinel-cli)")
class TestValidateArtifactSentinel(unittest.TestCase):
    @staticmethod
    def _script_path() -> Path:
        return Path(__file__).resolve().parent.parent / "scripts" / "validate_artifact_sentinel.py"

    def _run(self, input_path: str, schema_path: str) -> tuple[int, str]:
        proc = subprocess.run(
            [sys.executable, str(self._script_path()), "--input", input_path, "--schema", schema_path],
            check=False,
            capture_output=True,
            text=True,
        )
        out = proc.stdout + proc.stderr
        return proc.returncode, out

    def test_pass(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            sp = root / "schema.json"
            sp.write_text(SCHEMA_TEXT, encoding="utf-8")
            op = root / "out.json"
            op.write_text(
                json.dumps({"name": "A", "age": 1, "city": "B"}, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            code, out = self._run(str(op), str(sp))
            self.assertEqual(code, 0, out)
            self.assertIn("PASS: Contract satisfied", out)

    def test_fail_schema(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            sp = root / "schema.json"
            sp.write_text(SCHEMA_TEXT, encoding="utf-8")
            op = root / "out.json"
            op.write_text(
                json.dumps({"name": "A", "city": "B"}),
                encoding="utf-8",
            )
            code, out = self._run(str(op), str(sp))
            self.assertEqual(code, 1, out)
            self.assertIn("FAIL: Contract violated", out)
            self.assertIn("SCHEMA_VALIDATION_ERROR", out)

    def test_error_missing_file(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            sp = root / "schema.json"
            sp.write_text(SCHEMA_TEXT, encoding="utf-8")
            code, out = self._run(str(root / "missing.json"), str(sp))
            self.assertEqual(code, 2, out)
            self.assertIn("ERROR: Execution failed", out)

    def test_error_invalid_json(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            sp = root / "schema.json"
            sp.write_text(SCHEMA_TEXT, encoding="utf-8")
            op = root / "out.json"
            op.write_text("not json {{{", encoding="utf-8")
            code, out = self._run(str(op), str(sp))
            self.assertEqual(code, 2, out)
            self.assertIn("JSON_PARSE_ERROR", out)

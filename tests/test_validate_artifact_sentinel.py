import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

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


class TestValidateArtifactSentinel(unittest.TestCase):
    @staticmethod
    def _script_path() -> Path:
        return Path(__file__).resolve().parent.parent / "scripts" / "validate_artifact_sentinel.py"

    @staticmethod
    def _fake_sentinel_path(root: Path) -> Path:
        p = root / "fake_sentinel.sh"
        p.write_text(
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            "rc=\"${FAKE_SENTINEL_RC:-0}\"\n"
            "echo \"fake sentinel rc=${rc} args:$*\"\n"
            "exit \"${rc}\"\n",
            encoding="utf-8",
        )
        p.chmod(0o755)
        return p

    def _run(self, input_path: str, schema_path: str, env: dict[str, str] | None = None) -> tuple[int, str]:
        proc = subprocess.run(
            [sys.executable, str(self._script_path()), "--input", input_path, "--schema", schema_path],
            check=False,
            capture_output=True,
            text=True,
            env=env,
        )
        out = proc.stdout + proc.stderr
        return proc.returncode, out

    def test_pass(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            fake = self._fake_sentinel_path(root)
            env = dict(os.environ)
            env["SENTINEL_BIN"] = str(fake)
            env["FAKE_SENTINEL_RC"] = "0"
            sp = root / "schema.json"
            sp.write_text(SCHEMA_TEXT, encoding="utf-8")
            op = root / "out.json"
            op.write_text(
                json.dumps({"name": "A", "age": 1, "city": "B"}, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            code, out = self._run(str(op), str(sp), env=env)
            self.assertEqual(code, 0, out)
            self.assertIn("PASS: Contract satisfied", out)

    def test_fail_schema(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            fake = self._fake_sentinel_path(root)
            env = dict(os.environ)
            env["SENTINEL_BIN"] = str(fake)
            env["FAKE_SENTINEL_RC"] = "1"
            sp = root / "schema.json"
            sp.write_text(SCHEMA_TEXT, encoding="utf-8")
            op = root / "out.json"
            op.write_text(
                json.dumps({"name": "A", "city": "B"}),
                encoding="utf-8",
            )
            code, out = self._run(str(op), str(sp), env=env)
            self.assertEqual(code, 1, out)
            self.assertIn("FAIL: Contract violated", out)
            self.assertIn("fake sentinel rc=1", out)

    def test_execution_failure_maps_to_exit_two(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            fake = self._fake_sentinel_path(root)
            env = dict(os.environ)
            env["SENTINEL_BIN"] = str(fake)
            env["FAKE_SENTINEL_RC"] = "2"
            sp = root / "schema.json"
            sp.write_text(SCHEMA_TEXT, encoding="utf-8")
            op = root / "out.json"
            op.write_text(json.dumps({"name": "A", "age": 1, "city": "B"}), encoding="utf-8")
            code, out = self._run(str(op), str(sp), env=env)
            self.assertEqual(code, 2, out)
            self.assertIn("ERROR: Execution failed", out)
            self.assertIn("fake sentinel rc=2", out)

    def test_error_missing_sentinel_cli(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            env = dict(os.environ)
            env["SENTINEL_BIN"] = str(root / "does-not-exist")
            sp = root / "schema.json"
            sp.write_text(SCHEMA_TEXT, encoding="utf-8")
            op = root / "out.json"
            op.write_text(json.dumps({"name": "A", "age": 1, "city": "B"}), encoding="utf-8")
            code, out = self._run(str(op), str(sp), env=env)
            self.assertEqual(code, 2, out)
            self.assertIn("SENTINEL_CLI_NOT_FOUND", out)

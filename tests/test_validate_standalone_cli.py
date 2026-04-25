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


class TestValidateStandaloneCli(unittest.TestCase):
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

    @staticmethod
    def _schema_text() -> str:
        return json.dumps(
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

    def _run_cli(self, argv: list[str], env: dict[str, str] | None = None) -> tuple[int, str]:
        out = io.StringIO()
        with patch("sys.argv", argv), patch.dict(os.environ, env or {}, clear=False), redirect_stdout(out):
            exit_code = cli.main()
        return exit_code, out.getvalue()

    def test_validate_success_exit_zero(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            fake = self._fake_sentinel_path(root)
            schema = root / "schema.json"
            artifact = root / "artifact.json"
            schema.write_text(self._schema_text(), encoding="utf-8")
            artifact.write_text(json.dumps({"name": "A", "age": 1, "city": "B"}), encoding="utf-8")
            code, out = self._run_cli(
                ["extract", "validate", "--input", str(artifact), "--schema", str(schema)],
                env={"SENTINEL_BIN": str(fake), "FAKE_SENTINEL_RC": "0"},
            )
            self.assertEqual(code, 0)
            self.assertIn("PASS: Contract satisfied", out)
            self.assertIn("fake sentinel rc=0", out)
            self.assertEqual(out.count("PASS: Contract satisfied"), 1)

    def test_validate_contract_failure_exit_one(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            fake = self._fake_sentinel_path(root)
            schema = root / "schema.json"
            artifact = root / "artifact.json"
            schema.write_text(self._schema_text(), encoding="utf-8")
            artifact.write_text(json.dumps({"name": "A"}), encoding="utf-8")
            code, out = self._run_cli(
                ["extract", "validate", "--input", str(artifact), "--schema", str(schema)],
                env={"SENTINEL_BIN": str(fake), "FAKE_SENTINEL_RC": "1"},
            )
            self.assertEqual(code, 1)
            self.assertIn("FAIL: Contract violated", out)
            self.assertEqual(out.count("FAIL: Contract violated"), 1)

    def test_validate_execution_failure_exit_two(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            fake = self._fake_sentinel_path(root)
            schema = root / "schema.json"
            artifact = root / "artifact.json"
            schema.write_text(self._schema_text(), encoding="utf-8")
            artifact.write_text(json.dumps({"name": "A", "age": 1, "city": "B"}), encoding="utf-8")
            code, out = self._run_cli(
                ["extract", "validate", "--input", str(artifact), "--schema", str(schema)],
                env={"SENTINEL_BIN": str(fake), "FAKE_SENTINEL_RC": "2"},
            )
            self.assertEqual(code, 2)
            self.assertIn("ERROR: Execution failed", out)

    def test_validate_failure_output_written_on_failure(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            fake = self._fake_sentinel_path(root)
            schema = root / "schema.json"
            artifact = root / "artifact.json"
            failure_output = root / "failure.json"
            schema.write_text(self._schema_text(), encoding="utf-8")
            artifact.write_text(json.dumps({"name": "A"}), encoding="utf-8")
            code, _ = self._run_cli(
                [
                    "extract",
                    "validate",
                    "--input",
                    str(artifact),
                    "--schema",
                    str(schema),
                    "--failure-output",
                    str(failure_output),
                ],
                env={"SENTINEL_BIN": str(fake), "FAKE_SENTINEL_RC": "1"},
            )
            self.assertEqual(code, 1)
            self.assertTrue(failure_output.exists())
            payload = json.loads(failure_output.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "FAIL")
            self.assertEqual(payload["sentinel_exit_code"], 1)
            self.assertIn("fake sentinel rc=1", payload["stdout"])
            self.assertEqual(payload["stderr"], "")

    def test_validate_failure_output_not_written_on_success(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            fake = self._fake_sentinel_path(root)
            schema = root / "schema.json"
            artifact = root / "artifact.json"
            failure_output = root / "failure.json"
            schema.write_text(self._schema_text(), encoding="utf-8")
            artifact.write_text(json.dumps({"name": "A", "age": 1, "city": "B"}), encoding="utf-8")
            code, _ = self._run_cli(
                [
                    "extract",
                    "validate",
                    "--input",
                    str(artifact),
                    "--schema",
                    str(schema),
                    "--failure-output",
                    str(failure_output),
                ],
                env={"SENTINEL_BIN": str(fake), "FAKE_SENTINEL_RC": "0"},
            )
            self.assertEqual(code, 0)
            self.assertFalse(failure_output.exists())

    def test_validate_success_output_written_on_success(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            fake = self._fake_sentinel_path(root)
            schema = root / "schema.json"
            artifact = root / "artifact.json"
            success_output = root / "success.json"
            schema.write_text(self._schema_text(), encoding="utf-8")
            artifact.write_text(json.dumps({"name": "A", "age": 1, "city": "B"}), encoding="utf-8")
            code, _ = self._run_cli(
                [
                    "extract",
                    "validate",
                    "--input",
                    str(artifact),
                    "--schema",
                    str(schema),
                    "--success-output",
                    str(success_output),
                ],
                env={"SENTINEL_BIN": str(fake), "FAKE_SENTINEL_RC": "0"},
            )
            self.assertEqual(code, 0)
            self.assertTrue(success_output.exists())
            payload = json.loads(success_output.read_text(encoding="utf-8"))
            self.assertEqual(payload["exit_code"], 0)
            self.assertIn("fake sentinel rc=0", payload["stdout"])
            self.assertEqual(payload["stderr"], "")

    def test_validate_success_output_omitted_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            fake = self._fake_sentinel_path(root)
            schema = root / "schema.json"
            artifact = root / "artifact.json"
            success_output = root / "success.json"
            schema.write_text(self._schema_text(), encoding="utf-8")
            artifact.write_text(json.dumps({"name": "A", "age": 1, "city": "B"}), encoding="utf-8")
            code, _ = self._run_cli(
                [
                    "extract",
                    "validate",
                    "--input",
                    str(artifact),
                    "--schema",
                    str(schema),
                ],
                env={"SENTINEL_BIN": str(fake), "FAKE_SENTINEL_RC": "0"},
            )
            self.assertEqual(code, 0)
            self.assertFalse(success_output.exists())

    def test_validate_success_output_not_written_on_failure(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            fake = self._fake_sentinel_path(root)
            schema = root / "schema.json"
            artifact = root / "artifact.json"
            success_output = root / "success.json"
            failure_output = root / "failure.json"
            schema.write_text(self._schema_text(), encoding="utf-8")
            artifact.write_text(json.dumps({"name": "A"}), encoding="utf-8")
            code, _ = self._run_cli(
                [
                    "extract",
                    "validate",
                    "--input",
                    str(artifact),
                    "--schema",
                    str(schema),
                    "--success-output",
                    str(success_output),
                    "--failure-output",
                    str(failure_output),
                ],
                env={"SENTINEL_BIN": str(fake), "FAKE_SENTINEL_RC": "1"},
            )
            self.assertEqual(code, 1)
            self.assertFalse(success_output.exists())
            self.assertTrue(failure_output.exists())

    def test_validate_without_failure_output_remains_optional(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            fake = self._fake_sentinel_path(root)
            schema = root / "schema.json"
            artifact = root / "artifact.json"
            schema.write_text(self._schema_text(), encoding="utf-8")
            artifact.write_text(json.dumps({"name": "A"}), encoding="utf-8")
            code, out = self._run_cli(
                ["extract", "validate", "--input", str(artifact), "--schema", str(schema)],
                env={"SENTINEL_BIN": str(fake), "FAKE_SENTINEL_RC": "1"},
            )
            self.assertEqual(code, 1)
            self.assertIn("FAIL: Contract violated", out)


if __name__ == "__main__":
    unittest.main()

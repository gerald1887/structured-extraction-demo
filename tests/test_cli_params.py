import io
import sys
import tempfile
import types
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.modules.setdefault("openai", types.SimpleNamespace(OpenAI=object))

from extractor import cli
from extractor.runner import BatchRunResult, RunResult


class DummyProvider:
    def generate(self, prompt: str, model: str, temperature: float, max_tokens: int | None) -> str:
        return "{}"


class TestCliParams(unittest.TestCase):
    def _run_cli(self, argv: list[str]):
        out = io.StringIO()
        with patch("extractor.cli.OpenAIProvider", DummyProvider), patch("sys.argv", argv), redirect_stdout(out):
            exit_code = cli.main()
        return exit_code, out.getvalue()

    def test_single_mode_passes_temperature_and_max_tokens(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            input_file = root / "in.txt"
            output_file = root / "out.json"
            schema_file = root / "schema.json"
            input_file.write_text("x", encoding="utf-8")
            schema_file.write_text("{}", encoding="utf-8")

            with patch("extractor.cli.run_extraction", return_value=RunResult(success=True)) as mock_run:
                exit_code, stdout = self._run_cli(
                    [
                        "extract",
                        "run",
                        "--input",
                        str(input_file),
                        "--schema",
                        str(schema_file),
                        "--output",
                        str(output_file),
                        "--temperature",
                        "0.5",
                        "--max-tokens",
                        "123",
                    ]
                )

            self.assertEqual(exit_code, 0)
            self.assertEqual(stdout, "SUCCESS\n")
            kwargs = mock_run.call_args.kwargs
            self.assertEqual(kwargs["temperature"], 0.5)
            self.assertEqual(kwargs["max_tokens"], 123)
            self.assertIsNone(kwargs["capture_output_path"])
            self.assertIsNone(kwargs["replay_output_path"])
            self.assertIsNone(kwargs["redaction_config_path"])

    def test_batch_mode_passes_temperature_default_and_none_max_tokens(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            input_dir = root / "in"
            output_dir = root / "out"
            schema_file = root / "schema.json"
            input_dir.mkdir()
            output_dir.mkdir()
            schema_file.write_text("{}", encoding="utf-8")

            with patch(
                "extractor.cli.run_batch_extraction",
                return_value=BatchRunResult(total=0, success=0, contract_failure=0, execution_error=0),
            ) as mock_run:
                exit_code, stdout = self._run_cli(
                    [
                        "extract",
                        "run",
                        "--input-dir",
                        str(input_dir),
                        "--schema",
                        str(schema_file),
                        "--output-dir",
                        str(output_dir),
                    ]
                )

            self.assertEqual(exit_code, 0)
            self.assertEqual(stdout, "total=0\nsuccess=0\ncontract_failure=0\nexecution_error=0\n")
            kwargs = mock_run.call_args.kwargs
            self.assertEqual(kwargs["temperature"], 0.0)
            self.assertIsNone(kwargs["max_tokens"])
            self.assertIsNone(kwargs["capture_output_path"])
            self.assertIsNone(kwargs["replay_output_path"])
            self.assertIsNone(kwargs["redaction_config_path"])

    def test_single_mode_passes_capture_and_replay_args(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            input_file = root / "in.txt"
            output_file = root / "out.json"
            schema_file = root / "schema.json"
            replay_file = root / "replay.txt"
            capture_file = root / "capture.txt"
            input_file.write_text("x", encoding="utf-8")
            replay_file.write_text("{}", encoding="utf-8")
            schema_file.write_text("{}", encoding="utf-8")

            with patch("extractor.cli.run_extraction", return_value=RunResult(success=True)) as mock_run:
                exit_code, stdout = self._run_cli(
                    [
                        "extract",
                        "run",
                        "--input",
                        str(input_file),
                        "--schema",
                        str(schema_file),
                        "--output",
                        str(output_file),
                        "--capture-output",
                        str(capture_file),
                    ]
                )

            self.assertEqual(exit_code, 0)
            self.assertEqual(stdout, "SUCCESS\n")
            kwargs = mock_run.call_args.kwargs
            self.assertEqual(kwargs["capture_output_path"], str(capture_file))
            self.assertIsNone(kwargs["replay_output_path"])
            self.assertIsNone(kwargs["redaction_config_path"])

            with patch("extractor.cli.run_extraction", return_value=RunResult(success=True)) as mock_run:
                exit_code, stdout = self._run_cli(
                    [
                        "extract",
                        "run",
                        "--input",
                        str(input_file),
                        "--schema",
                        str(schema_file),
                        "--output",
                        str(output_file),
                        "--replay-output",
                        str(replay_file),
                    ]
                )

            self.assertEqual(exit_code, 0)
            self.assertEqual(stdout, "SUCCESS\n")
            kwargs = mock_run.call_args.kwargs
            self.assertIsNone(kwargs["capture_output_path"])
            self.assertEqual(kwargs["replay_output_path"], str(replay_file))
            self.assertIsNone(kwargs["redaction_config_path"])

            redaction_file = root / "redaction.json"
            redaction_file.write_text('{"rules":[]}', encoding="utf-8")
            with patch("extractor.cli.run_extraction", return_value=RunResult(success=True)) as mock_run:
                exit_code, stdout = self._run_cli(
                    [
                        "extract",
                        "run",
                        "--input",
                        str(input_file),
                        "--schema",
                        str(schema_file),
                        "--output",
                        str(output_file),
                        "--redaction-config",
                        str(redaction_file),
                    ]
                )
            self.assertEqual(exit_code, 0)
            self.assertEqual(stdout, "SUCCESS\n")
            kwargs = mock_run.call_args.kwargs
            self.assertEqual(kwargs["redaction_config_path"], str(redaction_file))


if __name__ == "__main__":
    unittest.main()

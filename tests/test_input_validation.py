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
from extractor.input_validation import MAX_INPUT_BYTES
from extractor.runner import run_extraction


class CountingProvider:
    name = "test"

    def __init__(self) -> None:
        self.calls = 0

    def generate(self, prompt: str, model: str, temperature: float, max_tokens: int | None) -> str:
        self.calls += 1
        return json.dumps({"name": "John", "age": 30, "city": "Bangalore"})


def _write_schema(root: Path) -> Path:
    schema = root / "schema.json"
    schema.write_text(
        json.dumps(
            {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "age": {"type": "number"},
                    "city": {"type": "string"},
                },
                "required": ["name", "age", "city"],
            }
        ),
        encoding="utf-8",
    )
    return schema


class TestInputValidation(unittest.TestCase):
    def _run_cli(self, argv: list[str], provider_class=CountingProvider):
        out = io.StringIO()
        with patch("extractor.cli.OpenAIProvider", provider_class), patch("sys.argv", argv), redirect_stdout(out):
            code = cli.main()
        return code, out.getvalue()

    def test_empty_input_file_fails_and_provider_not_called(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            input_file = root / "in.txt"
            input_file.write_text("", encoding="utf-8")
            schema = _write_schema(root)
            output = root / "out.json"
            provider = CountingProvider()
            result = run_extraction(str(input_file), str(schema), str(output), "m", provider)
            self.assertFalse(result.success)
            self.assertEqual(result.error.error_type, "FILE_ERROR")
            self.assertEqual(result.error.message, "Input is empty")
            self.assertEqual(provider.calls, 0)

            code, out = self._run_cli(
                [
                    "extract",
                    "run",
                    "--input",
                    str(input_file),
                    "--schema",
                    str(schema),
                    "--output",
                    str(output),
                ]
            )
            self.assertEqual(code, 2)
            self.assertEqual(out, "ERROR FILE_ERROR Input is empty\n")
            self.assertFalse(output.exists())

    def test_oversized_input_file_fails_and_provider_not_called(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            input_file = root / "in.txt"
            input_file.write_bytes(b"a" * (MAX_INPUT_BYTES + 1))
            schema = _write_schema(root)
            output = root / "out.json"
            provider = CountingProvider()
            result = run_extraction(str(input_file), str(schema), str(output), "m", provider)
            self.assertFalse(result.success)
            self.assertEqual(result.error.error_type, "FILE_ERROR")
            self.assertEqual(result.error.message, f"Input exceeds max size limit: {MAX_INPUT_BYTES} bytes")
            self.assertEqual(provider.calls, 0)

    def test_invalid_utf8_input_file_fails_and_provider_not_called(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            input_file = root / "in.txt"
            input_file.write_bytes(b"\xff\xfe\xfd")
            schema = _write_schema(root)
            output = root / "out.json"
            provider = CountingProvider()
            result = run_extraction(str(input_file), str(schema), str(output), "m", provider)
            self.assertFalse(result.success)
            self.assertEqual(result.error.error_type, "FILE_ERROR")
            self.assertEqual(result.error.message, "Input is not valid UTF-8")
            self.assertEqual(provider.calls, 0)


if __name__ == "__main__":
    unittest.main()

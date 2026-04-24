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


class ParseErrorProvider:
    name = "test"

    def generate(self, prompt: str, model: str, temperature: float, max_tokens: int | None) -> str:
        return "```json {not valid} ```"


class SchemaMissingFieldProvider:
    name = "test"

    def generate(self, prompt: str, model: str, temperature: float, max_tokens: int | None) -> str:
        return json.dumps({"name": "John", "city": "Bangalore"})


class SchemaTypeMismatchProvider:
    name = "test"

    def generate(self, prompt: str, model: str, temperature: float, max_tokens: int | None) -> str:
        return json.dumps({"name": "John", "age": "thirty", "city": "Bangalore"})


class ExtraFieldProvider:
    name = "test"

    def generate(self, prompt: str, model: str, temperature: float, max_tokens: int | None) -> str:
        return json.dumps({"name": "John", "age": 30, "city": "Bangalore", "country": "India"})


class StrictValidProvider:
    name = "test"

    def generate(self, prompt: str, model: str, temperature: float, max_tokens: int | None) -> str:
        return json.dumps({"name": "John", "age": 30, "city": "Bangalore"})


class TestContractBoundaries(unittest.TestCase):
    def _run_cli(self, argv: list[str], provider_class):
        out = io.StringIO()
        with patch("extractor.cli.OpenAIProvider", provider_class), patch("sys.argv", argv), redirect_stdout(out):
            exit_code = cli.main()
        return exit_code, out.getvalue()

    def _setup_files(self, root: Path) -> tuple[Path, Path, Path]:
        input_file = root / "input.txt"
        schema_file = root / "schema.json"
        output_file = root / "output.json"
        input_file.write_text("John lives in Bangalore and is 30 years old.", encoding="utf-8")
        schema_file.write_text(SCHEMA_TEXT, encoding="utf-8")
        return input_file, schema_file, output_file

    def _setup_files_with_schema(self, root: Path, schema: dict) -> tuple[Path, Path, Path]:
        input_file = root / "input.txt"
        schema_file = root / "schema.json"
        output_file = root / "output.json"
        input_file.write_text("John lives in Bangalore and is 30 years old.", encoding="utf-8")
        schema_file.write_text(json.dumps(schema), encoding="utf-8")
        return input_file, schema_file, output_file

    def test_json_parse_error_boundary(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            input_file, schema_file, output_file = self._setup_files(root)
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
                ],
                provider_class=ParseErrorProvider,
            )

            self.assertEqual(exit_code, 1)
            self.assertEqual(stdout, "ERROR JSON_PARSE_ERROR Invalid JSON returned by model\n")
            self.assertFalse(output_file.exists())

    def test_schema_validation_missing_required_boundary(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            input_file, schema_file, output_file = self._setup_files(root)
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
                ],
                provider_class=SchemaMissingFieldProvider,
            )

            self.assertEqual(exit_code, 1)
            self.assertEqual(stdout, "ERROR SCHEMA_VALIDATION_ERROR Missing required field: age\n")
            self.assertFalse(output_file.exists())

    def test_schema_validation_type_mismatch_boundary(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            input_file, schema_file, output_file = self._setup_files(root)
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
                ],
                provider_class=SchemaTypeMismatchProvider,
            )

            self.assertEqual(exit_code, 1)
            self.assertEqual(stdout, "ERROR SCHEMA_VALIDATION_ERROR Schema validation failed\n")
            self.assertFalse(output_file.exists())

    def test_extra_field_strict_schema_boundary(self):
        strict_schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "number"},
                "city": {"type": "string"},
            },
            "required": ["name", "age", "city"],
            "additionalProperties": False,
        }
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            input_file, schema_file, output_file = self._setup_files_with_schema(root, strict_schema)
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
                ],
                provider_class=ExtraFieldProvider,
            )

            self.assertEqual(exit_code, 1)
            self.assertEqual(stdout, "ERROR SCHEMA_VALIDATION_ERROR Schema validation failed\n")
            self.assertFalse(output_file.exists())

    def test_valid_strict_output_boundary_success(self):
        strict_schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "number"},
                "city": {"type": "string"},
            },
            "required": ["name", "age", "city"],
            "additionalProperties": False,
        }
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            input_file, schema_file, output_file = self._setup_files_with_schema(root, strict_schema)
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
                ],
                provider_class=StrictValidProvider,
            )

            self.assertEqual(exit_code, 0)
            self.assertEqual(stdout, "SUCCESS\n")
            self.assertTrue(output_file.exists())


if __name__ == "__main__":
    unittest.main()

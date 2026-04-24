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
from extractor.output import write_output_json


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


class FakeProvider:
    name = "test"

    def __init__(self, *args, **kwargs):
        pass

    def generate(self, prompt: str, model: str, temperature: float, max_tokens: int | None) -> str:
        if "PROVIDERERR" in prompt:
            raise Exception("provider fail")
        return json.dumps({"name": "John Doe", "age": 30, "city": "Bangalore"})


class TestCanonicalFormatting(unittest.TestCase):
    def _run_cli(self, argv: list[str], provider_class=FakeProvider):
        out = io.StringIO()
        with patch("extractor.cli.OpenAIProvider", provider_class), patch("sys.argv", argv), redirect_stdout(out):
            exit_code = cli.main()
        return exit_code, out.getvalue()

    def _write_schema(self, root: Path) -> Path:
        path = root / "schema.json"
        path.write_text(SCHEMA_TEXT, encoding="utf-8")
        return path

    def _assert_canonical(self, content: str) -> None:
        self.assertTrue(content.endswith("\n"))
        self.assertFalse(content.endswith("\n\n"))
        for line in content.splitlines():
            self.assertEqual(line, line.rstrip(" "))

    def test_output_writer_sorts_top_level_and_nested_keys(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "out.json"
            data = {"z": 1, "a": {"y": 2, "x": 1}, "m": [{"b": 2, "a": 1}]}
            write_output_json(str(path), data)
            content = path.read_text(encoding="utf-8")
            self._assert_canonical(content)
            expected = (
                '{\n'
                '  "a": {\n'
                '    "x": 1,\n'
                '    "y": 2\n'
                '  },\n'
                '  "m": [\n'
                '    {\n'
                '      "a": 1,\n'
                '      "b": 2\n'
                "    }\n"
                "  ],\n"
                '  "z": 1\n'
                "}\n"
            )
            self.assertEqual(content, expected)

    def test_equivalent_dict_writes_are_byte_identical(self):
        with tempfile.TemporaryDirectory() as td:
            p1 = Path(td) / "a.json"
            p2 = Path(td) / "b.json"
            write_output_json(str(p1), {"b": {"d": 4, "c": 3}, "a": 1})
            write_output_json(str(p2), {"a": 1, "b": {"c": 3, "d": 4}})
            self.assertEqual(p1.read_bytes(), p2.read_bytes())

    def test_metadata_artifact_is_canonical(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            input_file = root / "input.txt"
            output_file = root / "output.json"
            schema = self._write_schema(root)
            input_file.write_text("John Doe is 30 years old and lives in Bangalore.", encoding="utf-8")
            code, out = self._run_cli(
                [
                    "extract",
                    "run",
                    "--input",
                    str(input_file),
                    "--schema",
                    str(schema),
                    "--output",
                    str(output_file),
                ]
            )
            self.assertEqual(code, 0)
            self.assertEqual(out, "SUCCESS\n")
            meta_path = Path(f"{output_file}.meta.json")
            content = meta_path.read_text(encoding="utf-8")
            self._assert_canonical(content)
            parsed = json.loads(content)
            self.assertEqual(content, json.dumps(parsed, indent=2, sort_keys=True) + "\n")

    def test_error_artifact_is_canonical(self):
        class ProviderErr:
            name = "test"

            def __init__(self, *args, **kwargs):
                pass

            def generate(self, prompt: str, model: str, temperature: float, max_tokens: int | None) -> str:
                raise Exception("provider blew up")

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            input_file = root / "input.txt"
            output_file = root / "output.json"
            schema = self._write_schema(root)
            input_file.write_text("data", encoding="utf-8")
            code, out = self._run_cli(
                [
                    "extract",
                    "run",
                    "--input",
                    str(input_file),
                    "--schema",
                    str(schema),
                    "--output",
                    str(output_file),
                ],
                provider_class=ProviderErr,
            )
            self.assertEqual(code, 2)
            self.assertEqual(out, "ERROR INTERNAL_ERROR Internal error\n")
            err_path = Path(f"{output_file}.error.json")
            content = err_path.read_text(encoding="utf-8")
            self._assert_canonical(content)
            parsed = json.loads(content)
            self.assertEqual(content, json.dumps(parsed, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    unittest.main()

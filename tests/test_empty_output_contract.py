import json
import tempfile
import unittest
from pathlib import Path

from extractor.errors import EMPTY_OUTPUT_ERROR
from extractor.runner import run_extraction


class EmptyProvider:
    name = "test"

    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def generate(self, prompt: str, model: str, temperature: float, max_tokens: int | None) -> str:
        return json.dumps(self.payload)


class TestEmptyOutputContract(unittest.TestCase):
    def _schema(self, root: Path) -> Path:
        schema = root / "schema.json"
        schema.write_text(
            json.dumps(
                {
                    "type": "object",
                    "properties": {
                        "name": {"type": ["string", "null"]},
                        "age": {"type": ["number", "null"]},
                        "city": {"type": ["string", "null"]},
                        "tags": {"type": "array"},
                        "extra": {"type": "object"},
                    },
                    "required": ["name", "age", "city", "tags", "extra"],
                }
            ),
            encoding="utf-8",
        )
        return schema

    def test_fail_on_empty_flags_recursively_empty_payload(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            schema = self._schema(root)
            inp = root / "input.txt"
            out = root / "out.json"
            inp.write_text("x", encoding="utf-8")
            provider = EmptyProvider({"name": "", "age": None, "city": "", "tags": [], "extra": {}})

            result = run_extraction(str(inp), str(schema), str(out), "m", provider, fail_on_empty=True)
            self.assertFalse(result.success)
            self.assertEqual(result.error.error_type, EMPTY_OUTPUT_ERROR)

    def test_fail_on_empty_ignores_meta_key_for_emptiness(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            schema = self._schema(root)
            inp = root / "input.txt"
            out = root / "out.json"
            inp.write_text("x", encoding="utf-8")
            provider = EmptyProvider(
                {"name": "", "age": None, "city": "", "tags": [], "extra": {}, "_meta": {"anything": "x"}}
            )

            result = run_extraction(str(inp), str(schema), str(out), "m", provider, fail_on_empty=True)
            self.assertFalse(result.success)
            self.assertEqual(result.error.error_type, EMPTY_OUTPUT_ERROR)

    def test_without_fail_on_empty_no_contract_failure(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            schema = self._schema(root)
            inp = root / "input.txt"
            out = root / "out.json"
            inp.write_text("x", encoding="utf-8")
            provider = EmptyProvider({"name": "", "age": None, "city": "", "tags": [], "extra": {}})

            result = run_extraction(str(inp), str(schema), str(out), "m", provider, fail_on_empty=False)
            self.assertTrue(result.success)


if __name__ == "__main__":
    unittest.main()

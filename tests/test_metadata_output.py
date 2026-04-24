import json
import tempfile
import unittest
from pathlib import Path

from extractor.runner import run_extraction


class MetadataProvider:
    name = "test"

    def generate(self, prompt: str, model: str, temperature: float, max_tokens: int | None) -> str:
        return json.dumps({"name": "John Doe", "age": 30, "city": "Bangalore"})


class TestMetadataOutput(unittest.TestCase):
    def test_output_is_pure_payload_and_metadata_contains_fields(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            input_file = root / "sample.txt"
            schema_file = root / "schema.json"
            output_file = root / "out.json"
            input_file.write_text("John Doe is 30 years old and lives in Bangalore.", encoding="utf-8")
            schema_file.write_text(
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

            result = run_extraction(
                input_path=str(input_file),
                schema_path=str(schema_file),
                output_path=str(output_file),
                model="gpt-4.1-mini",
                provider=MetadataProvider(),
                temperature=0.0,
                max_tokens=None,
            )

            self.assertTrue(result.success)
            data = json.loads(output_file.read_text(encoding="utf-8"))
            self.assertNotIn("_meta", data)
            self.assertEqual(set(data.keys()), {"name", "age", "city"})
            meta = json.loads(Path(f"{output_file}.meta.json").read_text(encoding="utf-8"))
            self.assertIn("input_file", meta)
            self.assertIn("model", meta)
            self.assertIn("provider", meta)
            self.assertIn("temperature", meta)
            self.assertIn("prompt_hash", meta)
            self.assertIn("redaction_applied", meta)
            self.assertFalse(meta["redaction_applied"])


if __name__ == "__main__":
    unittest.main()

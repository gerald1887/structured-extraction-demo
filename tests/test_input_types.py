import json
import tempfile
import unittest
from pathlib import Path

from extractor.runner import run_batch_extraction, run_extraction


class EchoProvider:
    name = "test"

    def __init__(self) -> None:
        self.prompts: list[str] = []

    def generate(self, prompt: str, model: str, temperature: float, max_tokens: int | None) -> str:
        self.prompts.append(prompt)
        return json.dumps({"name": "John", "age": 30, "city": "Bangalore"})


class TestInputTypes(unittest.TestCase):
    def _schema(self, root: Path) -> Path:
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

    def test_single_file_supports_txt_md_json(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            schema = self._schema(root)
            provider = EchoProvider()

            txt = root / "a.txt"
            md = root / "b.md"
            js = root / "c.json"
            txt.write_text("Alpha", encoding="utf-8")
            md.write_text("Beta", encoding="utf-8")
            js.write_text(json.dumps({"x": "Gamma"}), encoding="utf-8")

            self.assertTrue(
                run_extraction(str(txt), str(schema), str(root / "a_out.json"), "m", provider).success
            )
            self.assertTrue(
                run_extraction(str(md), str(schema), str(root / "b_out.json"), "m", provider).success
            )
            self.assertTrue(
                run_extraction(str(js), str(schema), str(root / "c_out.json"), "m", provider).success
            )

    def test_json_extraction_depth_first_left_to_right(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            schema = self._schema(root)
            provider = EchoProvider()
            js = root / "c.json"
            js.write_text(
                json.dumps(
                    {
                        "a": "first",
                        "b": ["second", {"c": "third"}],
                        "d": {"e": "fourth"},
                        "x": 1,
                    }
                ),
                encoding="utf-8",
            )

            result = run_extraction(str(js), str(schema), str(root / "out.json"), "m", provider)
            self.assertTrue(result.success)
            self.assertIn("first second third fourth", provider.prompts[-1])

    def test_batch_mixed_extensions_supported(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            schema = self._schema(root)
            input_dir = root / "inputs"
            output_dir = root / "outputs"
            input_dir.mkdir()
            provider = EchoProvider()

            (input_dir / "a.md").write_text("one", encoding="utf-8")
            (input_dir / "b.txt").write_text("two", encoding="utf-8")
            (input_dir / "c.json").write_text(json.dumps({"k": "three"}), encoding="utf-8")

            result = run_batch_extraction(str(input_dir), str(schema), str(output_dir), "m", provider)
            self.assertEqual(result.total, 3)
            self.assertEqual(result.success, 3)
            self.assertTrue((output_dir / "a.json").exists())
            self.assertTrue((output_dir / "b.json").exists())
            self.assertTrue((output_dir / "c.json").exists())


if __name__ == "__main__":
    unittest.main()

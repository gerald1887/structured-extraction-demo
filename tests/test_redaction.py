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
from extractor.redaction import apply_redaction, load_redaction_config


class FakeProvider:
    name = "test"

    def __init__(self, *args, **kwargs):
        pass

    def generate(self, prompt: str, model: str, temperature: float, max_tokens: int | None) -> str:
        if "Alpha" in prompt:
            return json.dumps(
                {
                    "name": "Alice",
                    "email": "alice@example.com",
                    "address": {"city": "Paris", "zip": "75000"},
                    "tags": ["pii:alice@example.com", "ok"],
                }
            )
        return json.dumps({"name": "John", "email": "john@example.com"})


class TestRedaction(unittest.TestCase):
    def _run_cli(self, argv: list[str], provider_class=FakeProvider):
        out = io.StringIO()
        with patch("extractor.cli.OpenAIProvider", provider_class), patch("sys.argv", argv), redirect_stdout(out):
            exit_code = cli.main()
        return exit_code, out.getvalue()

    def _write_schema(self, root: Path) -> Path:
        path = root / "schema.json"
        path.write_text(
            json.dumps(
                {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "email": {"type": "string"},
                        "address": {
                            "type": "object",
                            "properties": {"city": {"type": "string"}, "zip": {"type": "string"}},
                            "required": ["city", "zip"],
                        },
                        "tags": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["name", "email", "address", "tags"],
                }
            ),
            encoding="utf-8",
        )
        return path

    def test_invalid_redaction_config_returns_deterministic_message(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            input_file = root / "in.txt"
            schema = self._write_schema(root)
            output = root / "out.json"
            bad_cfg = root / "bad.json"
            input_file.write_text("Alpha", encoding="utf-8")
            bad_cfg.write_text("{not-json", encoding="utf-8")
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
                    "--redaction-config",
                    str(bad_cfg),
                ]
            )
            self.assertEqual(code, 2)
            self.assertEqual(out, "ERROR INTERNAL_ERROR Invalid redaction config\n")

    def test_invalid_regex_pattern_returns_deterministic_message(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cfg = root / "cfg.json"
            cfg.write_text(json.dumps({"rules": [{"match_type": "regex_replace", "action": "mask", "pattern": "["}]}))
            with self.assertRaisesRegex(Exception, "Invalid regex pattern"):
                load_redaction_config(str(cfg))

    def test_rules_apply_in_config_order_and_regex_on_string_leaf_only(self):
        data = {
            "name": "Alice",
            "email": "alice@example.com",
            "nested": {"email": "leaf@example.com", "count": 2},
            "list": ["leaf@example.com", {"email": "x@example.com"}],
        }
        config = {
            "rules": [
                {"match_type": "exact_key", "action": "mask", "key": "email", "mask_value": "M"},
                {"match_type": "regex_replace", "action": "replace_constant", "pattern": "M", "value": "R"},
            ]
        }
        out = apply_redaction(data, config)
        self.assertEqual(out["email"], "R")
        self.assertEqual(out["nested"]["email"], "R")
        self.assertEqual(out["nested"]["count"], 2)
        self.assertEqual(out["list"][0], "leaf@example.com")
        self.assertEqual(out["list"][1]["email"], "R")

    def test_fail_on_empty_runs_after_redaction(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            input_file = root / "in.txt"
            schema = root / "schema.json"
            output = root / "out.json"
            cfg = root / "cfg.json"
            input_file.write_text("x", encoding="utf-8")
            schema.write_text(
                json.dumps(
                    {
                        "type": "object",
                        "properties": {"name": {"type": "string"}},
                        "required": ["name"],
                    }
                ),
                encoding="utf-8",
            )
            cfg.write_text(
                json.dumps({"rules": [{"match_type": "exact_key", "action": "replace_constant", "key": "name", "value": ""}]}),
                encoding="utf-8",
            )

            class NameProvider:
                name = "test"

                def __init__(self, *args, **kwargs):
                    pass

                def generate(self, prompt: str, model: str, temperature: float, max_tokens: int | None) -> str:
                    return json.dumps({"name": "X"})

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
                    "--redaction-config",
                    str(cfg),
                    "--fail-on-empty",
                ],
                provider_class=NameProvider,
            )
            self.assertEqual(code, 1)
            self.assertEqual(out, "ERROR EMPTY_OUTPUT_ERROR Semantically empty output\n")

    def test_metadata_has_redaction_applied_only(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            input_file = root / "in.txt"
            schema = self._write_schema(root)
            output = root / "out.json"
            cfg = root / "cfg.json"
            input_file.write_text("Alpha", encoding="utf-8")
            cfg.write_text(json.dumps({"rules": [{"match_type": "exact_key", "action": "mask", "key": "email"}]}), encoding="utf-8")
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
                    "--redaction-config",
                    str(cfg),
                ]
            )
            self.assertEqual(code, 0)
            self.assertEqual(out, "SUCCESS\n")
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertNotIn("_meta", payload)
            self.assertEqual(payload["email"], "***")
            meta = json.loads(Path(f"{output}.meta.json").read_text(encoding="utf-8"))
            self.assertTrue(meta["redaction_applied"])

    def test_batch_uses_same_config_independently(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            input_dir = root / "in"
            input_dir.mkdir()
            output_dir = root / "out"
            output_dir.mkdir()
            schema = self._write_schema(root)
            cfg = root / "cfg.json"
            cfg.write_text(json.dumps({"rules": [{"match_type": "exact_key", "action": "mask", "key": "email"}]}), encoding="utf-8")
            (input_dir / "a.txt").write_text("Alpha", encoding="utf-8")
            (input_dir / "b.txt").write_text("Alpha", encoding="utf-8")
            code, out = self._run_cli(
                [
                    "extract",
                    "run",
                    "--input-dir",
                    str(input_dir),
                    "--schema",
                    str(schema),
                    "--output-dir",
                    str(output_dir),
                    "--redaction-config",
                    str(cfg),
                ]
            )
            self.assertEqual(code, 0)
            self.assertEqual(out, "total=2\nsuccess=2\ncontract_failure=0\nexecution_error=0\n")
            self.assertEqual(json.loads((output_dir / "a.json").read_text(encoding="utf-8"))["email"], "***")
            self.assertEqual(json.loads((output_dir / "b.json").read_text(encoding="utf-8"))["email"], "***")

    def test_redacted_output_is_byte_identical_across_identical_runs(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            input_file = root / "in.txt"
            schema = self._write_schema(root)
            out1 = root / "r1.json"
            out2 = root / "r2.json"
            cfg = root / "cfg.json"
            input_file.write_text("Alpha", encoding="utf-8")
            cfg.write_text(
                json.dumps(
                    {
                        "rules": [
                            {"match_type": "exact_key", "action": "mask", "key": "email"},
                            {
                                "match_type": "json_pointer",
                                "action": "replace_constant",
                                "pointer": "/address/city",
                                "value": "REDACTED",
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            code1, out_text1 = self._run_cli(
                [
                    "extract",
                    "run",
                    "--input",
                    str(input_file),
                    "--schema",
                    str(schema),
                    "--output",
                    str(out1),
                    "--redaction-config",
                    str(cfg),
                ]
            )
            code2, out_text2 = self._run_cli(
                [
                    "extract",
                    "run",
                    "--input",
                    str(input_file),
                    "--schema",
                    str(schema),
                    "--output",
                    str(out2),
                    "--redaction-config",
                    str(cfg),
                ]
            )
            self.assertEqual(code1, 0)
            self.assertEqual(code2, 0)
            self.assertEqual(out_text1, "SUCCESS\n")
            self.assertEqual(out_text2, "SUCCESS\n")
            self.assertEqual(out1.read_bytes(), out2.read_bytes())

    def test_repo_sample_redaction_config_is_valid(self):
        config_path = Path(__file__).resolve().parent.parent / "redaction" / "sample_config.json"
        config = load_redaction_config(str(config_path))
        self.assertIsInstance(config, dict)
        self.assertIn("rules", config)
        self.assertIsInstance(config["rules"], list)

    def test_json_pointer_remove_field_deletes_list_element(self):
        data = {"tags": ["pii:alice", "ok"]}
        config = {"rules": [{"match_type": "json_pointer", "action": "remove_field", "pointer": "/tags/0"}]}
        out = apply_redaction(data, config)
        self.assertEqual(out, {"tags": ["ok"]})


if __name__ == "__main__":
    unittest.main()

import unittest

from extractor.hash_utils import compute_sha256
from extractor.prompt_builder import build_prompt


class TestPromptHash(unittest.TestCase):
    def test_same_inputs_same_hash(self):
        template = "Schema:\n{{schema}}\nText:\n{{input_text}}"
        schema_text = '{"type":"object"}'
        input_text = "John Doe"
        prompt_a = build_prompt(template=template, schema_text=schema_text, input_text=input_text)
        prompt_b = build_prompt(template=template, schema_text=schema_text, input_text=input_text)
        self.assertEqual(compute_sha256(prompt_a), compute_sha256(prompt_b))

    def test_different_input_text_different_hash(self):
        template = "Schema:\n{{schema}}\nText:\n{{input_text}}"
        schema_text = '{"type":"object"}'
        prompt_a = build_prompt(template=template, schema_text=schema_text, input_text="John Doe")
        prompt_b = build_prompt(template=template, schema_text=schema_text, input_text="Jane Doe")
        self.assertNotEqual(compute_sha256(prompt_a), compute_sha256(prompt_b))


if __name__ == "__main__":
    unittest.main()

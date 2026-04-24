import unittest

from extractor.preprocess import preprocess_text


class TestPreprocess(unittest.TestCase):
    def test_normalizes_line_endings_and_collapses_whitespace(self):
        text = "a\r\nb\rc\n\t d"
        self.assertEqual(preprocess_text(text), "a b c d")

    def test_removes_control_chars_except_line_tab_before_collapse(self):
        text = "a\x00b\x1fc\t\nd"
        self.assertEqual(preprocess_text(text), "abc d")

    def test_strips_raw_fence_tokens(self):
        text = "```hello~~~ world```"
        self.assertEqual(preprocess_text(text), "hello world")


if __name__ == "__main__":
    unittest.main()

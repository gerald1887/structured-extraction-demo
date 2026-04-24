import re


def preprocess_text(raw_text: str) -> str:
    text = raw_text.replace("\r\n", "\n").replace("\r", "\n")
    text = "".join(ch for ch in text if ch == "\n" or ch == "\t" or ord(ch) >= 32)
    text = text.replace("```", "").replace("~~~", "")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


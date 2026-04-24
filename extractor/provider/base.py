from typing import Optional


class Provider:
    name: str

    def generate(self, prompt: str, model: str, temperature: float, max_tokens: Optional[int]) -> str:
        raise NotImplementedError


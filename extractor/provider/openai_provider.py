import os
from typing import Optional

from openai import OpenAI

from extractor.errors import AppError, PROVIDER_ERROR
from extractor.provider.base import Provider


class OpenAIProvider(Provider):
    name = "openai"

    def __init__(self, simulate_provider_error: str | None = None) -> None:
        self._simulate_provider_error = simulate_provider_error
        if self._simulate_provider_error is not None:
            return
        if not os.environ.get("OPENAI_API_KEY"):
            raise AppError(PROVIDER_ERROR, "OPENAI_API_KEY not set")
        self._client = OpenAI()

    def generate(self, prompt: str, model: str, temperature: float, max_tokens: Optional[int]) -> str:
        if self._simulate_provider_error == "timeout":
            raise AppError(PROVIDER_ERROR, "Provider timeout (simulated)")
        if self._simulate_provider_error == "rate_limit":
            raise AppError(PROVIDER_ERROR, "Provider rate limit (simulated)")
        if self._simulate_provider_error == "invalid_response":
            raise AppError(PROVIDER_ERROR, "Provider invalid response (simulated)")
        try:
            request_kwargs = {
                "model": model,
                "temperature": temperature,
                "messages": [
                    {
                        "role": "system",
                        "content": "You must return ONLY valid JSON. No explanation, no markdown, no extra text.",
                    },
                    {"role": "user", "content": prompt},
                ],
            }
            if max_tokens is not None:
                request_kwargs["max_tokens"] = max_tokens
            response = self._client.chat.completions.create(**request_kwargs)
            content = response.choices[0].message.content
            if not isinstance(content, str) or not content.strip():
                raise AppError(PROVIDER_ERROR, "Provider request failed")
            return content
        except AppError:
            raise
        except Exception as exc:
            raise AppError(PROVIDER_ERROR, "Provider request failed") from exc


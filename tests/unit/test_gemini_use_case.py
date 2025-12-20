from __future__ import annotations

import pytest

from src.application.use_cases.filter_message_with_gemini import (
    FilterMessageWithGeminiUseCase,
)


class FakeGeminiClient:
    def __init__(self, response: str) -> None:
        self._response = response
        self.model_name = "fake-model"

    def generate_json(self, prompt: str) -> str:
        return self._response


@pytest.mark.asyncio
async def test_classify_parses_valid_json() -> None:
    client = FakeGeminiClient('{"pass": true, "score": 0.8, "reason": "ok"}')
    use_case = FilterMessageWithGeminiUseCase(client)

    result = await use_case.classify("hello", "jobs", "prompt")

    assert result.passed is True
    assert result.score == 0.8
    assert result.reason == "ok"
    assert result.model == "fake-model"
    assert result.prompt_name == "jobs"


@pytest.mark.asyncio
async def test_classify_handles_invalid_json() -> None:
    client = FakeGeminiClient("not-json")
    use_case = FilterMessageWithGeminiUseCase(client)

    with pytest.raises(ValueError):
        await use_case.classify("hello", "jobs", "prompt")


@pytest.mark.asyncio
async def test_classify_sanitizes_score() -> None:
    client = FakeGeminiClient('{"pass": false, "score": 2, "reason": "x"}')
    use_case = FilterMessageWithGeminiUseCase(client)

    result = await use_case.classify("hello", "jobs", "prompt")

    assert result.score == 1.0

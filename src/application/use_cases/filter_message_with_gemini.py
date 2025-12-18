"""Use case to evaluate Telegram messages via Gemini."""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass

from src.infrastructure.llm_gemini import GeminiFilterClient

PROMPT_NAME = "default"
PROMPT_VERSION = "v1"
PROMPT_SUFFIX = """
Return ONLY valid minified JSON in the format:
{"pass": true/false, "score": 0.0-1.0, "reason": "short explanation"}

Rules:
- JSON must be the entire response: no markdown, comments, or surrounding text.
- "score" must always be a float between 0 and 1.
- Keep "reason" under 120 characters.
- If the message lacks relevant info, set pass=false with a short reason.
"""


@dataclass
class GeminiFilterDecision:
    passed: bool
    score: float
    reason: str
    model: str
    prompt_name: str
    prompt_version: str


class FilterMessageWithGeminiUseCase:
    """Runs message text through Gemini and returns classification."""

    def __init__(
        self,
        gemini_client: GeminiFilterClient,
        logger: logging.Logger | None = None,
    ) -> None:
        self._gemini_client = gemini_client
        self._logger = logger or logging.getLogger("collector.gemini_use_case")

    async def classify(
        self,
        message_text: str,
        category_name: str,
        category_prompt: str,
    ) -> GeminiFilterDecision:
        prompt = self._build_prompt(category_prompt, message_text)
        raw_response = await asyncio.to_thread(self._gemini_client.generate_json, prompt)
        decision = self._parse_response(raw_response)
        decision.prompt_name = category_name
        self._logger.info(
            '[LLM][category=%s] pass=%s score=%.2f reason="%s"',
            category_name,
            decision.passed,
            decision.score,
            decision.reason,
        )
        return decision

    def _build_prompt(self, category_prompt: str, message_text: str) -> str:
        return (
            f"{category_prompt}\n\n{PROMPT_SUFFIX}\n\nMessage:\n<<<\n{message_text}\n>>>\nJSON:"
        )

    def _parse_response(self, raw: str) -> GeminiFilterDecision:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Gemini returned invalid JSON: {raw}") from exc
        passed = bool(payload.get("pass", False))
        score = self._sanitize_score(payload.get("score"))
        reason = str(payload.get("reason") or "No reason provided").strip()
        return GeminiFilterDecision(
            passed=passed,
            score=score,
            reason=reason[:200],
            model=self._gemini_client.model_name,
            prompt_name=PROMPT_NAME,
            prompt_version=PROMPT_VERSION,
        )

    @staticmethod
    def _sanitize_score(value) -> float:
        try:
            score = float(value)
        except (TypeError, ValueError):
            return 0.0
        return max(0.0, min(1.0, score))

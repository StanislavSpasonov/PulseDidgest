"""Use case to evaluate Telegram messages via Gemini."""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Optional

try:
    from telethon.events.newmessage import NewMessage
except ModuleNotFoundError:  # pragma: no cover - telethon not installed locally
    NewMessage = object  # type: ignore

from src.infrastructure.llm_gemini import GeminiFilterClient

CATEGORY_DESCRIPTION = (
    "Tech and product job opportunities relevant for Berlin-based professionals."
)
PROMPT_NAME = "default"
PROMPT_VERSION = "v1"
PROMPT_TEMPLATE = """
You are PulseDidgest's category filter. Assess the Telegram message below for this category:
"{category}".

Return ONLY valid minified JSON in the format:
{{"pass": true/false, "score": 0.0-1.0, "reason": "short explanation"}}

Rules:
- JSON must be the entire response: no markdown, comments, or surrounding text.
- "score" must always be a float between 0 and 1.
- Keep "reason" under 120 characters.
- If the message lacks relevant info, set pass=false with a short reason.

Message:
<<<
{message}
>>>
JSON:
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
    """Runs every Telegram message through Gemini and logs the decision."""

    def __init__(
        self,
        gemini_client: GeminiFilterClient,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self._gemini_client = gemini_client
        self._logger = logger or logging.getLogger("collector.gemini_use_case")

    async def handle(self, event: NewMessage.Event) -> Optional[GeminiFilterDecision]:  # type: ignore[name-defined]
        message = getattr(event, "message", None)
        if message is None:
            self._logger.warning("Gemini filter received empty event: %s", event)
            return None

        text = getattr(message, "message", "") or ""
        text = text.strip()
        if not text:
            self._logger.info("Gemini filter skipped message without text: id=%s", getattr(message, "id", None))
            return None

        try:
            decision = await self._classify_text(text)
        except Exception as exc:  # pragma: no cover - runtime guard
            self._logger.error("Gemini classification failed: %s", exc)
            return None

        self._logger.info(
            '[LLM] pass=%s score=%.2f reason="%s"',
            decision.passed,
            decision.score,
            decision.reason,
        )
        return decision

    async def _classify_text(self, message_text: str) -> GeminiFilterDecision:
        prompt = PROMPT_TEMPLATE.format(
            category=CATEGORY_DESCRIPTION,
            message=message_text,
        )
        raw_response = await asyncio.to_thread(self._gemini_client.generate_json, prompt)
        return self._parse_response(raw_response)

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

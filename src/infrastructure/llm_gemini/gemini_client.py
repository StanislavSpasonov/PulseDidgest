"""Simple Gemini client wrapper for the collector MVP."""
from __future__ import annotations

import logging
from typing import Optional

try:
    import google.generativeai as genai
except ModuleNotFoundError as exc:  # pragma: no cover - optional during local dev
    raise RuntimeError(
        "google-generativeai is required to use the Gemini client"
    ) from exc


class GeminiFilterClient:
    """Thin wrapper around the Gemini SDK."""

    def __init__(
        self,
        api_key: str,
        model_name: str = "gemini-1.5-flash",
        logger: Optional[logging.Logger] = None,
    ) -> None:
        if not api_key:
            raise ValueError("Gemini API key is required")

        self._logger = logger or logging.getLogger("collector.gemini_client")
        self._model_name = model_name
        genai.configure(api_key=api_key)
        self._model = genai.GenerativeModel(model_name)

    def generate_json(self, prompt: str) -> str:
        """Calls Gemini with the provided prompt and returns raw text."""
        self._logger.debug("Calling Gemini model=%s", self._model_name)
        response = self._model.generate_content(prompt)
        text = getattr(response, "text", None)
        if text:
            return text.strip()

        candidates = getattr(response, "candidates", None) or []
        parts: list[str] = []
        for candidate in candidates:
            content = getattr(candidate, "content", None)
            if not content:
                continue
            for part in getattr(content, "parts", []) or []:
                value = getattr(part, "text", None)
                if value:
                    parts.append(value)
        return "".join(parts).strip()

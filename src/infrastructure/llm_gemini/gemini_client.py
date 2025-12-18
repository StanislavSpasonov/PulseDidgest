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
        model_name: Optional[str] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        if not api_key:
            raise ValueError("Gemini API key is required")

        self._logger = logger or logging.getLogger("collector.gemini_client")
        genai.configure(api_key=api_key)
        resolved_model = self._resolve_model_name(explicit_name=model_name)
        self._model_name = resolved_model
        self._model = genai.GenerativeModel(resolved_model)
        self._logger.info("Using Gemini model: %s", resolved_model)

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

    def _resolve_model_name(self, explicit_name: Optional[str]) -> str:
        if explicit_name:
            self._logger.info("Using Gemini model from env: %s", explicit_name)
            return explicit_name

        fallback = self._find_first_supported_model()
        if fallback:
            self._logger.info(
                "GEMINI_MODEL not set; falling back to first generateContent model: %s",
                fallback,
            )
            return fallback

        raise RuntimeError(
            "Could not find Gemini model supporting generateContent. "
            "Set GEMINI_MODEL or run python apps/tools/list_gemini_models.py"
        )

    @staticmethod
    def _find_first_supported_model() -> Optional[str]:
        for model in genai.list_models():
            methods = getattr(model, "generation_methods", []) or []
            if "generateContent" in methods:
                return getattr(model, "name", None)
        return None

    @property
    def model_name(self) -> str:
        return self._model_name

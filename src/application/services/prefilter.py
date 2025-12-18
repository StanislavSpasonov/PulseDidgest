"""Prefilter helper utilities for categories."""
from __future__ import annotations

from typing import Tuple

from src.domain.entities import PrefilterRule


def should_run_llm(message_text: str, rule: PrefilterRule) -> Tuple[bool, str | None]:
    text = message_text or ""
    normalized = text.lower()
    length = len(text.strip())

    if rule.min_length and length < rule.min_length:
        return False, f"length<{rule.min_length}"

    if rule.include_any:
        if not any(term in normalized for term in rule.include_any):
            return False, "include_any"

    if rule.exclude_any:
        if any(term in normalized for term in rule.exclude_any):
            return False, "exclude_any"

    return True, None

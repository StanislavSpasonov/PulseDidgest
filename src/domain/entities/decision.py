"""Domain entity representing an LLM decision."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DecisionRecord:
    model: str
    prompt_name: str
    prompt_version: str
    passed: bool
    score: float
    reason: str

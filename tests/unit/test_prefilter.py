from __future__ import annotations

from src.application.services.prefilter import should_run_llm
from src.domain.entities import PrefilterRule


def test_prefilter_min_length() -> None:
    rule = PrefilterRule(min_length=5, include_any=None, exclude_any=None)
    allowed, reason = should_run_llm("hey", rule)
    assert allowed is False
    assert reason == "length<5"


def test_prefilter_include_any() -> None:
    rule = PrefilterRule(min_length=None, include_any=["job"], exclude_any=None)
    allowed, reason = should_run_llm("hello world", rule)
    assert allowed is False
    assert reason == "include_any"


def test_prefilter_exclude_any() -> None:
    rule = PrefilterRule(min_length=None, include_any=None, exclude_any=["crypto"])
    allowed, reason = should_run_llm("crypto jobs", rule)
    assert allowed is False
    assert reason == "exclude_any"


def test_prefilter_allows_match() -> None:
    rule = PrefilterRule(min_length=3, include_any=["job"], exclude_any=["spam"])
    allowed, reason = should_run_llm("Job offer", rule)
    assert allowed is True
    assert reason is None

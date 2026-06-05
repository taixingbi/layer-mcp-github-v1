"""Tests for LLM source formatting and context budget helpers."""

from __future__ import annotations

import os

import pytest

from app.ask.citations import (
    clamp_llm_user_body,
    format_multi_repo_sources,
    multi_repo_readme_cap,
)


def test_multi_repo_readme_cap_scales_down_with_repo_count(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_USER_BODY_MAX_CHARS", "4000")
    cap_nine = multi_repo_readme_cap(9, code_hit_count=20)
    cap_one = multi_repo_readme_cap(1, code_hit_count=20)
    assert cap_nine < cap_one
    assert cap_nine <= 400


def test_format_multi_repo_sources_respects_scaled_readme_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_USER_BODY_MAX_CHARS", "4000")
    readmes = {f"owner/repo-{i}": "x" * 5000 for i in range(9)}
    body = format_multi_repo_sources([], readmes, [])
    assert len(body) < 9 * 5000
    for i in range(9):
        assert ("x" * 500) not in body or f"repo-{i}" in body


def test_clamp_llm_user_body_hard_caps(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_USER_BODY_MAX_CHARS", "100")
    out = clamp_llm_user_body("a" * 200)
    assert len(out) <= 100
    assert out.endswith("LLM context limit]")

"""Synthesis prompt content for github_search."""

import pytest

from app.ask.common import chat_messages
from app.ask.prompts import BLOCKS_SYSTEM_PROMPT, TEXT_SYSTEM_PROMPT, system_prompt


def test_text_prompt_architecture_rules(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_SEARCH_ANSWER_FORMAT", "text")
    prompt = system_prompt()
    assert prompt == TEXT_SYSTEM_PROMPT
    assert "120" not in TEXT_SYSTEM_PROMPT
    assert "clarifies service flow" in TEXT_SYSTEM_PROMPT
    assert "250 words" in TEXT_SYSTEM_PROMPT
    assert "environment variables" in TEXT_SYSTEM_PROMPT
    assert "middleware" in TEXT_SYSTEM_PROMPT
    assert "endpoint" in TEXT_SYSTEM_PROMPT
    assert "implementation" in TEXT_SYSTEM_PROMPT
    assert "debug" in TEXT_SYSTEM_PROMPT


def test_blocks_prompt_service_rules(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_SEARCH_ANSWER_FORMAT", "blocks")
    prompt = system_prompt()
    assert prompt == BLOCKS_SYSTEM_PROMPT
    assert "120" not in BLOCKS_SYSTEM_PROMPT
    assert "endpoint: optional" in BLOCKS_SYSTEM_PROMPT
    assert "what/why/data flow" in BLOCKS_SYSTEM_PROMPT
    assert "Deep dive trigger" in BLOCKS_SYSTEM_PROMPT


def test_chat_messages_uses_system_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_SEARCH_ANSWER_FORMAT", "text")
    messages = chat_messages("Repository: org/repo\nUser question: hi")
    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == system_prompt()
    assert messages[1]["role"] == "user"

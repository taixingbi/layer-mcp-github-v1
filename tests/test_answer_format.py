"""Answer format selection (text vs blocks)."""

import pytest

from app.ask.blocks import ANSWER_FORMAT_BLOCKS, ANSWER_FORMAT_TEXT, resolve_answer_content


def test_resolve_answer_content_text_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITHUB_SEARCH_ANSWER_FORMAT", raising=False)
    content = resolve_answer_content("Hello [1]\n\n- item [2]")
    assert content.format == ANSWER_FORMAT_TEXT
    assert content.text == "Hello [1]\n\n- item [2]"
    assert content.blocks == []


def test_resolve_answer_content_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_SEARCH_ANSWER_FORMAT", "blocks")
    raw = '{"blocks": [{"type": "paragraph", "text": "Hi", "cite_ids": [1]}], "notes": []}'
    content = resolve_answer_content(raw)
    assert content.format == ANSWER_FORMAT_BLOCKS
    assert content.blocks[0]["type"] == "paragraph"

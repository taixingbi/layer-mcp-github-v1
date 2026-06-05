"""Structured answer block parsing and rendering."""

from __future__ import annotations

import json

from app.ask.blocks import (
    ANSWER_FORMAT_BLOCKS,
    blocks_to_text,
    iter_text_chunks,
    parse_structured_answer,
)
from app.ask.response import build_answer_payload


def test_parse_structured_answer_service_blocks() -> None:
    raw = json.dumps(
        {
            "blocks": [
                {"type": "heading", "text": "Gateway Architecture", "cite_ids": []},
                {
                    "type": "service",
                    "name": "layer-gateway-inference-v1",
                    "role": "inference",
                    "description": "Routes chat completions",
                    "cite_ids": [4],
                },
            ],
            "notes": ["Health checks not documented"],
        }
    )
    content = parse_structured_answer(raw)
    assert content.format == ANSWER_FORMAT_BLOCKS
    assert len(content.blocks) == 2
    assert content.notes == ["Health checks not documented"]
    assert "layer-gateway-inference-v1" in content.text
    assert "[4]" in content.text


def test_parse_structured_answer_fallback_paragraph() -> None:
    content = parse_structured_answer("Plain legacy answer [1]")
    assert len(content.blocks) == 1
    assert content.blocks[0]["type"] == "paragraph"
    assert content.text == "Plain legacy answer [1]"


def test_build_answer_payload_includes_blocks() -> None:
    from app.ask.blocks import AnswerContent

    payload = build_answer_payload(
        answer_content=AnswerContent(
            text="Summary",
            blocks=[{"type": "paragraph", "text": "Summary", "cite_ids": []}],
            notes=["gap"],
        ),
        internal_citations=[{"index": 1, "label": "README"}],
    )
    assert payload["format"] == "blocks"
    assert payload["blocks"][0]["type"] == "paragraph"
    assert payload["notes"] == ["gap"]
    assert payload["citations"] == [{"cite_id": 1, "source": "README"}]


def test_iter_text_chunks() -> None:
    assert list(iter_text_chunks("abcdef", chunk_size=2)) == ["ab", "cd", "ef"]


def test_blocks_to_text_list() -> None:
    text = blocks_to_text(
        [{"type": "list", "items": ["one", "two"], "cite_ids": [2]}],
        notes=["missing detail"],
    )
    assert "- one [2]" in text
    assert "**Notes**" in text

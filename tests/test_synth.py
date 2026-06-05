"""Synth backend selection and Cursor SDK adapter (mocked)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.synth.cursor_sdk import CursorSdkSynth, _format_synth_prompt, _parse_follow_ups
from app.synth.legacy import LegacySynth


def test_format_synth_prompt_includes_ask_mode() -> None:
    body = _format_synth_prompt("Repository: taixingbi/foo\nUser question: hi")
    assert "read-only Ask mode" in body
    assert "taixingbi/foo" in body


def test_parse_follow_ups_json() -> None:
    raw = '{"follow_up_questions": ["a", "b", "c", "d"]}'
    assert _parse_follow_ups(raw) == ["a", "b", "c"]


def test_legacy_prereq_requires_gateway(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LLM_GATEWAY_BASE_URL", raising=False)
    assert LegacySynth().prereq_error() is not None


def test_cursor_prereq_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CURSOR_API_KEY", "")
    assert CursorSdkSynth().prereq_error() is not None


@patch("cursor_sdk.Agent")
def test_cursor_buffered_calls_prompt(mock_agent: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CURSOR_API_KEY", "cursor_test_key")
    monkeypatch.setenv("SYNTH_ENGINE", "cursor_sdk")

    chat_result = MagicMock(status="finished", result="Answer [1]", run_id="run-1")
    follow_result = MagicMock(
        status="finished",
        result='{"follow_up_questions": ["q1", "q2", "q3"]}',
        run_id="run-2",
    )
    mock_agent.prompt.side_effect = [chat_result, follow_result]

    synth = CursorSdkSynth()
    with httpx.Client() as client:
        answer, follow_ups, latency, chat_usage, follow_usage = synth.buffered(
            client,
            question="what?",
            user_body="sources here",
            scope_label="taixingbi/foo",
            conversation_id="conv-1",
            request_id="req-1",
            session_id="ses-1",
            trace_id=None,
            user=None,
        )

    assert answer == "Answer [1]"
    assert follow_ups == ["q1", "q2", "q3"]
    assert latency["chat"] >= 0
    assert chat_usage["total_tokens"] == 0
    assert mock_agent.prompt.call_count == 2


@patch("app.synth.base.synth_engine", return_value="legacy")
def test_get_synth_backend_legacy(_mock_engine: MagicMock) -> None:
    from app.synth import get_synth_backend

    assert isinstance(get_synth_backend(), LegacySynth)


@patch("app.synth.base.synth_engine", return_value="cursor_sdk")
def test_get_synth_backend_cursor(_mock_engine: MagicMock) -> None:
    from app.synth import get_synth_backend

    assert isinstance(get_synth_backend(), CursorSdkSynth)

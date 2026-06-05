"""Follow-up generation gated by GITHUB_SEARCH_FOLLOW_UPS."""

from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest

from app.ask.blocks import AnswerContent
from app.synth.legacy import LegacySynth


def test_legacy_skips_follow_ups_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITHUB_SEARCH_FOLLOW_UPS", raising=False)
    monkeypatch.setenv("LLM_GATEWAY_BASE_URL", "http://gateway:8000")

    with patch("app.synth.legacy.chat_completion", return_value=('{"blocks":[]}', {})) as mock_chat:
        with patch("app.synth.legacy.generate_follow_ups") as mock_follow:
            with patch(
                "app.synth.legacy.parse_structured_answer",
                return_value=AnswerContent(text="answer", blocks=[], notes=[]),
            ):
                synth = LegacySynth()
                with httpx.Client() as client:
                    _answer, follow_ups, _lat, _chat_u, follow_u = synth.buffered(
                        client,
                        question="q",
                        user_body="body",
                        scope_label="org/repo",
                        conversation_id="c",
                        request_id="r",
                        session_id="s",
                        trace_id=None,
                        user=None,
                    )

    assert follow_ups == []
    assert follow_u["total_tokens"] == 0
    mock_chat.assert_called_once()
    mock_follow.assert_not_called()

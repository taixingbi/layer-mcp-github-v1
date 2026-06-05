"""Cursor SDK synthesis (Ask-mode emulation: read-only, sources in prompt)."""

from __future__ import annotations

import json
import time
from collections.abc import Iterator
from typing import Any

import httpx

from app.ask.blocks import AnswerContent, iter_text_chunks, parse_structured_answer
from app.ask.prompts import ASK_MODE_APPENDIX, FOLLOW_UP_PROMPT, SYSTEM_PROMPT
from app.config import cursor_api_key, cursor_model, cursor_runtime_cwd
from app.observability.correlation import UserContext
from app.observability.logging_config import logger

_EMPTY_USAGE: dict[str, int] = {
    "prompt_tokens": 0,
    "completion_tokens": 0,
    "total_tokens": 0,
}


def _format_synth_prompt(user_body: str) -> str:
    return (
        f"{SYSTEM_PROMPT}\n\n{ASK_MODE_APPENDIX}\n\n"
        f"---\nSources and question:\n{user_body}"
    )


def _format_follow_up_prompt(question: str, answer: str, scope_label: str) -> str:
    return (
        f"{FOLLOW_UP_PROMPT}\n\n"
        f"Repositories: {scope_label}\nQuestion: {question}\nAnswer: {answer}"
    )


def _agent_options():
    from cursor_sdk import AgentOptions, LocalAgentOptions

    return AgentOptions(
        api_key=cursor_api_key(),
        model=cursor_model(),
        local=LocalAgentOptions(cwd=cursor_runtime_cwd(), setting_sources=[]),
    )


def _extract_result_text(result: Any) -> str:
    text = getattr(result, "result", None)
    if text is None:
        return ""
    return str(text).strip()


def _run_agent_prompt(prompt: str) -> tuple[str, str | None]:
    """Return (answer_text, cursor_run_id). Raises ValueError on run failure."""
    from cursor_sdk import Agent, CursorAgentError

    try:
        result = Agent.prompt(prompt, _agent_options())
    except CursorAgentError as exc:
        raise ValueError(f"Cursor SDK startup failed: {exc}") from exc

    run_id = getattr(result, "run_id", None) or getattr(result, "id", None)
    run_id_str = str(run_id) if run_id else None

    status = getattr(result, "status", None)
    if status == "error":
        raise ValueError(f"Cursor SDK run failed: {run_id_str or 'unknown'}")

    answer = _extract_result_text(result)
    if not answer:
        raise ValueError("Cursor SDK returned no content")
    return answer, run_id_str


def _parse_follow_ups(content: str) -> list[str]:
    try:
        parsed = json.loads(content)
        items = parsed.get("follow_up_questions") or []
        if isinstance(items, list):
            return [str(x).strip() for x in items if str(x).strip()][:3]
    except json.JSONDecodeError:
        pass
    return []


class CursorSdkSynth:
    """Synthesize answers via Cursor SDK Agent (read-only Ask-style prompt)."""

    def prereq_error(self) -> str | None:
        if not cursor_api_key():
            return "CURSOR_API_KEY not set in .env (required for SYNTH_ENGINE=cursor_sdk)"
        return None

    def buffered(
        self,
        client: httpx.Client,
        *,
        question: str,
        user_body: str,
        scope_label: str,
        conversation_id: str,
        request_id: str,
        session_id: str,
        trace_id: str | None,
        user: UserContext | None,
    ) -> tuple[str, list[str], dict[str, int], dict[str, int], dict[str, int]]:
        del client, conversation_id, request_id, session_id, trace_id, user
        latency: dict[str, int] = {}

        t_chat = time.perf_counter()
        raw_answer, run_id = _run_agent_prompt(_format_synth_prompt(user_body))
        answer_content = parse_structured_answer(raw_answer)
        answer = answer_content.text
        latency["chat"] = int((time.perf_counter() - t_chat) * 1000)
        if run_id:
            logger.info(
                "cursor_sdk chat done",
                extra={"cursor_run_id": run_id, "synth_engine": "cursor_sdk"},
            )

        t_follow = time.perf_counter()
        follow_content, follow_run_id = _run_agent_prompt(
            _format_follow_up_prompt(question, answer, scope_label)
        )
        follow_ups = _parse_follow_ups(follow_content)
        latency["follow_up_chat"] = int((time.perf_counter() - t_follow) * 1000)
        if follow_run_id:
            logger.info(
                "cursor_sdk follow_up done",
                extra={"cursor_run_id": follow_run_id, "synth_engine": "cursor_sdk"},
            )

        return answer, follow_ups, latency, dict(_EMPTY_USAGE), dict(_EMPTY_USAGE)

    def iter_stream(
        self,
        client: httpx.Client,
        *,
        user_body: str,
        conversation_id: str,
        request_id: str,
        session_id: str,
        trace_id: str | None,
        user: UserContext | None,
    ) -> Iterator[tuple[str, Any]]:
        del client, conversation_id, request_id, session_id, trace_id, user
        raw_answer, run_id = _run_agent_prompt(_format_synth_prompt(user_body))
        if run_id:
            logger.info(
                "cursor_sdk stream start",
                extra={"cursor_run_id": run_id, "synth_engine": "cursor_sdk"},
            )
        answer_content = parse_structured_answer(raw_answer)
        for chunk in iter_text_chunks(answer_content.text):
            yield ("delta", chunk)
        yield ("usage", dict(_EMPTY_USAGE))
        yield ("done", answer_content)

    def follow_ups(
        self,
        client: httpx.Client,
        *,
        question: str,
        answer: str,
        scope_label: str,
        conversation_id: str,
        request_id: str,
        session_id: str,
        trace_id: str | None,
        user: UserContext | None,
    ) -> tuple[list[str], dict[str, int]]:
        del client, conversation_id, request_id, session_id, trace_id, user
        follow_content, follow_run_id = _run_agent_prompt(
            _format_follow_up_prompt(question, answer, scope_label)
        )
        if follow_run_id:
            logger.info(
                "cursor_sdk follow_up done",
                extra={"cursor_run_id": follow_run_id, "synth_engine": "cursor_sdk"},
            )
        return _parse_follow_ups(follow_content), dict(_EMPTY_USAGE)

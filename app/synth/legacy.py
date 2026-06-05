"""Legacy synthesis via layer-gateway-inference."""

from __future__ import annotations

import time
from collections.abc import Iterator
from typing import Any

import httpx

from app.ask.common import chat_messages
from app.clients.llm import (
    chat_completion,
    generate_follow_ups,
    iter_chat_completion_stream,
    llm_gateway_base,
)
from app.observability.correlation import UserContext


class LegacySynth:
    """POST /v1/chat/completions on LLM_GATEWAY_BASE_URL."""

    def prereq_error(self) -> str | None:
        if not llm_gateway_base():
            return "LLM_GATEWAY_BASE_URL not set in .env (required to synthesize answers)"
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
        latency: dict[str, int] = {}
        messages = chat_messages(user_body)

        t_chat = time.perf_counter()
        answer, chat_usage = chat_completion(
            client,
            messages=messages,
            conversation_id=conversation_id,
            request_id=request_id,
            session_id=session_id,
            trace_id=trace_id,
            user=user,
        )
        latency["chat"] = int((time.perf_counter() - t_chat) * 1000)

        t_follow = time.perf_counter()
        follow_ups, follow_usage = generate_follow_ups(
            client,
            question,
            answer,
            scope_label,
            conversation_id=conversation_id,
            request_id=request_id,
            session_id=session_id,
            trace_id=trace_id,
            user=user,
        )
        latency["follow_up_chat"] = int((time.perf_counter() - t_follow) * 1000)
        return answer, follow_ups, latency, chat_usage, follow_usage

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
        return iter_chat_completion_stream(
            client,
            messages=chat_messages(user_body),
            conversation_id=conversation_id,
            request_id=request_id,
            session_id=session_id,
            trace_id=trace_id,
            user=user,
        )

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
        return generate_follow_ups(
            client,
            question,
            answer,
            scope_label,
            conversation_id=conversation_id,
            request_id=request_id,
            session_id=session_id,
            trace_id=trace_id,
            user=user,
        )

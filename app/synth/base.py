"""Synth backend protocol and factory."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any, Protocol

import httpx

from app.config import synth_engine
from app.observability.correlation import UserContext


class SynthBackend(Protocol):
    """Answer synthesis from GitHub evidence (user_body)."""

    def prereq_error(self) -> str | None:
        """Return error when required env is missing, else None."""

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
        """Chat + follow-ups; returns answer, follow_ups, latency slice, usages."""

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
        """Yield (``delta``, text), (``usage``, dict), (``done``, full text)."""

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
        """Suggest follow-up questions and return usage."""


def get_synth_backend() -> SynthBackend:
    """Return the configured synthesis backend."""
    if synth_engine() == "cursor_sdk":
        from .cursor_sdk import CursorSdkSynth

        return CursorSdkSynth()
    from .legacy import LegacySynth

    return LegacySynth()

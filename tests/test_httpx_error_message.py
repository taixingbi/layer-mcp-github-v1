"""Upstream error message classification."""

from __future__ import annotations

import httpx
import pytest

from app.ask.common import httpx_error_message


def _status_error(url: str, status: int = 400) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", url)
    response = httpx.Response(status, request=request)
    return httpx.HTTPStatusError("error", request=request, response=response)


def test_httpx_error_message_github() -> None:
    exc = _status_error("https://api.github.com/search/code")
    assert httpx_error_message(exc) == "GitHub API error: 400"


def test_httpx_error_message_llm_gateway() -> None:
    exc = _status_error(
        "http://layer-gateway-inference.ai-dev.svc.cluster.local:8000/v1/chat/completions"
    )
    assert httpx_error_message(exc) == "LLM gateway error: 400"

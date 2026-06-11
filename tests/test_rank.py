"""Repo routing from question text."""

from __future__ import annotations

from app.allowlist.rank import rank_repos_for_question


def test_ranks_gateway_inference_for_vllm_question() -> None:
    shorts = rank_repos_for_question(
        "in huntai, what gateway for vllm design?",
        max_repos=5,
    )
    assert "layer-gateway-inference-v1" in shorts
    assert len(shorts) <= 5


def test_explicit_layer_name_returns_single_repo() -> None:
    shorts = rank_repos_for_question(
        "explain layer-orchestrator-v1 routing",
        max_repos=5,
    )
    assert shorts == ["layer-orchestrator-v1"]


def test_fallback_platform_core_when_no_keywords() -> None:
    shorts = rank_repos_for_question("hello there", max_repos=4)
    assert "huntai-k3s" in shorts
    assert len(shorts) == 4

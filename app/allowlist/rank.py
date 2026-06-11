"""Question-based repo selection when ``repo`` is omitted (scope routing)."""

from __future__ import annotations

import os
import re

from app.allowlist.repos import ALLOWED_REPOS

# Platform overview questions with no keyword hits.
_DEFAULT_PLATFORM_SHORTS: tuple[str, ...] = (
    "huntai-k3s",
    "layer-orchestrator-v1",
    "layer-gateway-inference-v1",
    "layer-gateway-api-v1",
)

# Extra terms beyond the repo short name itself.
_REPO_TERMS: dict[str, tuple[str, ...]] = {
    "huntai-k3s": ("k3s", "kubernetes", "k8s", "gitops", "argocd", "cluster", "deploy"),
    "layer-gateway-api-v1": ("gateway", "gateway-api", "edge", "auth", "supabase", "bff"),
    "layer-gateway-inference-v1": (
        "gateway",
        "inference",
        "vllm",
        "completion",
        "completions",
        "gpu",
        "scheduler",
    ),
    "layer-gateway-embed-v1": ("gateway", "embed", "embedding", "embeddings"),
    "layer-gateway-reranker-v1": ("gateway", "rerank", "reranker", "reranking"),
    "layer-mcp-github-v1": ("mcp", "github_search", "github search"),
    "layer-orchestrator-v1": ("orchestrator", "intent", "router", "routing"),
    "layer-rag-ingest-v1": ("ingest", "ingestion", "qdrant"),
    "layer-rag-query-v1": ("rag", "retrieval", "query", "citation"),
    "layer-router-train-v1": ("router-train", "qlora", "dpo", "sft", "lora"),
    "layer-web-v1": ("web", "nextjs", "frontend", "ui", "chat page"),
}

_LAYER_NAME_RE = re.compile(r"\blayer-[a-z0-9-]+\b", re.I)
_OWNER_REPO_RE = re.compile(r"\b[\w.-]+/layer-[a-z0-9-]+\b", re.I)


def github_repo_routing_enabled() -> bool:
    """When true, omitting ``repo`` selects a ranked subset instead of full allowlist."""
    raw = (os.environ.get("GITHUB_REPO_ROUTING") or "true").strip().lower()
    return raw not in ("0", "false", "no", "off")


def github_route_max_repos() -> int:
    """Max repos to fetch when routing from question (floor 1)."""
    return max(1, int(os.environ.get("GITHUB_ROUTE_MAX_REPOS", "5")))


def _question_blob(question: str) -> str:
    return (question or "").strip().lower()


def _score_repo(short: str, blob: str) -> int:
    score = 0
    low = short.lower()
    stem = low.removesuffix("-v1")

    if low in blob or stem in blob:
        score += 12
    if f"taixingbi/{low}" in blob:
        score += 12

    for term in _REPO_TERMS.get(short, ()):
        if term in blob:
            score += 4

    return score


def rank_repos_for_question(
    question: str,
    shorts: list[str] | None = None,
    *,
    max_repos: int | None = None,
) -> list[str]:
    """Return up to ``max_repos`` allowlisted short names most relevant to ``question``."""
    allowed = list(shorts if shorts is not None else ALLOWED_REPOS)
    if not allowed:
        return []

    cap = max_repos if max_repos is not None else github_route_max_repos()
    cap = max(1, min(cap, len(allowed)))

    blob = _question_blob(question)
    if not blob:
        return _fallback_shorts(allowed, cap)

    for match in _OWNER_REPO_RE.findall(question or ""):
        short = match.split("/", 1)[-1].lower()
        if short in allowed:
            return [short]

    for match in _LAYER_NAME_RE.findall(question or ""):
        short = match.lower()
        if short in allowed:
            return [short]
        if f"{short}-v1" in allowed:
            return [f"{short}-v1"]

    scored = [( _score_repo(short, blob), short) for short in allowed]
    scored = [(s, name) for s, name in scored if s > 0]
    scored.sort(key=lambda item: (-item[0], item[1]))

    if scored:
        return [name for _, name in scored[:cap]]

    return _fallback_shorts(allowed, cap)


def _fallback_shorts(allowed: list[str], cap: int) -> list[str]:
    picked = [s for s in _DEFAULT_PLATFORM_SHORTS if s in allowed]
    if len(picked) < cap:
        for short in allowed:
            if short not in picked:
                picked.append(short)
            if len(picked) >= cap:
                break
    return picked[:cap]

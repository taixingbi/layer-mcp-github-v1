"""Citation numbering and LLM source formatting."""

from __future__ import annotations

from typing import Any

from app.ask.blog_links import citation_for_code_hit
from app.config import (
    LLM_CONTEXT_README_MAX,
    MULTI_REPO_README_MAX,
    SNIPPET_MAX,
    llm_user_body_max_chars,
)


def repo_web_url(full_name: str) -> str:
    """Canonical GitHub web URL for ``owner/repo``."""
    return f"https://github.com/{full_name}"


def build_citations(
    full_name: str,
    readme: str,
    code_hits: list[dict[str, str]],
    *,
    readme_label: str | None = None,
) -> list[dict[str, Any]]:
    """Numbered citations: README first, then deduped code file URLs."""
    citations: list[dict[str, Any]] = []
    idx = 1
    if readme:
        label = readme_label or "README"
        citations.append(
            {
                "index": idx,
                "url": repo_web_url(full_name),
                "label": label,
                "repo": full_name,
                "type": "repository",
            }
        )
        idx += 1
    seen_urls: set[str] = set()
    for hit in code_hits:
        row = citation_for_code_hit(hit, full_name=full_name)
        url = (row.get("url") or "").strip()
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        citations.append({"index": idx, **row})
        idx += 1
    if not citations:
        citations.append(
            {
                "index": 1,
                "url": repo_web_url(full_name),
                "label": full_name,
                "repo": full_name,
                "type": "repository",
            }
        )
    return citations


def merge_citations(repo_blocks: list[tuple[str, list[dict[str, Any]]]]) -> list[dict[str, Any]]:
    """Renumber citations across multiple repos into one contiguous list."""
    merged: list[dict[str, Any]] = []
    offset = 0
    for _full_name, block in repo_blocks:
        for c in block:
            merged.append({**c, "index": offset + int(c["index"])})
        offset = len(merged)
    return merged


def format_sources_for_llm(
    citations: list[dict[str, Any]], readme: str, code_hits: list[dict[str, str]]
) -> str:
    """Format single-repo sources block for the LLM user message."""
    lines = ["## Sources (use [n] in answer)"]
    for c in citations:
        lines.append(f"[{c['index']}] {c.get('label', '')} — {c['url']}")
    if readme:
        lines.append(f"\n## README excerpt\n{readme[:LLM_CONTEXT_README_MAX]}")
    if code_hits:
        lines.append("\n## Code snippets")
        for hit in code_hits:
            repo = hit.get("repo") or ""
            prefix = f"{repo}/" if repo else ""
            lines.append(f"### {prefix}{hit.get('path', '')}\n{hit.get('snippet') or '(no snippet)'}")
    return "\n".join(lines)


def multi_repo_readme_cap(repo_count: int, *, code_hit_count: int = 0) -> int:
    """Per-repo README excerpt length scaled to fit the gateway context window."""
    if repo_count <= 1:
        return MULTI_REPO_README_MAX
    budget = llm_user_body_max_chars()
    reserved = min(900, budget // 2) + min(repo_count * 60, 400)
    snippet_reserved = min(max(code_hit_count, 1) * 100, budget // 2)
    readme_pool = max(400, budget - reserved - snippet_reserved)
    per_repo = max(120, readme_pool // repo_count)
    return min(MULTI_REPO_README_MAX, per_repo)


def multi_repo_snippet_cap(code_hit_count: int) -> int:
    """Per-snippet cap for multi-repo code hits under a shared context budget."""
    if code_hit_count <= 0:
        return SNIPPET_MAX
    budget = llm_user_body_max_chars()
    snippet_pool = max(400, budget // 3)
    per_hit = max(80, snippet_pool // code_hit_count)
    return min(SNIPPET_MAX, per_hit)


def clamp_llm_user_body(text: str) -> str:
    """Hard cap on the LLM user message when proactive limits are still too large."""
    max_chars = llm_user_body_max_chars()
    if len(text) <= max_chars:
        return text
    suffix = "\n\n[... truncated for LLM context limit]"
    keep = max(0, max_chars - len(suffix))
    return text[:keep].rstrip() + suffix


def format_multi_repo_sources(
    citations: list[dict[str, Any]],
    readmes: dict[str, str],
    code_hits: list[dict[str, str]],
) -> str:
    """Format multi-repo sources block for the LLM user message."""
    repo_count = len(readmes) or 1
    hit_count = len(code_hits)
    readme_cap = multi_repo_readme_cap(repo_count, code_hit_count=hit_count)
    snippet_cap = multi_repo_snippet_cap(hit_count)

    lines = ["## Sources (use [n] in answer)"]
    for c in citations:
        lines.append(f"[{c['index']}] {c.get('label', '')} — {c['url']}")
    if readmes:
        lines.append("\n## README excerpts")
        for full_name, text in readmes.items():
            if text:
                lines.append(f"\n### {full_name}\n{text[:readme_cap]}")
    if code_hits:
        lines.append("\n## Code snippets")
        for hit in code_hits:
            repo = hit.get("repo") or ""
            snippet = (hit.get("snippet") or "(no snippet)")[:snippet_cap]
            lines.append(f"### {repo}/{hit.get('path', '')}\n{snippet}")
    return "\n".join(lines)

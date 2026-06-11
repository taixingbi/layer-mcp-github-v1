"""Parse GitHub tree URLs and optional path arguments for scoped search."""

from __future__ import annotations

import re

from app.config import github_search_default_tree_url

_GITHUB_TREE_RE = re.compile(
    r"https?://github\.com/(?P<owner>[^/\s]+)/(?P<repo>[^/\s]+)/tree/(?P<branch>[^/\s]+)(?:/(?P<path>[^\s?#]+))?",
    re.IGNORECASE,
)


def normalize_repo_path(path: str | None) -> str | None:
    """Strip slashes; return ``None`` when empty."""
    if not path:
        return None
    cleaned = str(path).strip().strip("/")
    return cleaned or None


def parse_github_tree_url(text: str) -> tuple[str, str | None] | None:
    """Return ``(repo_short_name, path)`` from a GitHub tree URL in ``text``."""
    match = _GITHUB_TREE_RE.search(text or "")
    if not match:
        return None
    repo = (match.group("repo") or "").strip()
    path = normalize_repo_path(match.group("path"))
    if not repo:
        return None
    return repo, path


def strip_github_urls(text: str) -> str:
    """Remove GitHub tree URLs from a question string."""
    return _GITHUB_TREE_RE.sub("", text or "").strip()


def default_path_question(path: str) -> str:
    """Fallback question when the user message is only a tree URL."""
    return f"What files, directories, and topics are in {path}?"


def _apply_tree_url(raw: str, *, path: str | None) -> tuple[str | None, str | None]:
    """Parse ``raw`` as repo short name or GitHub tree URL."""
    text = (raw or "").strip()
    if not text:
        return None, path
    parsed = parse_github_tree_url(text)
    if not parsed:
        return text, path
    url_repo, url_path = parsed
    if not normalize_repo_path(path) and url_path:
        path = url_path
    return url_repo, path


def resolve_search_inputs(
    repo: str | None,
    question: str,
    path: str | None = None,
) -> tuple[str | None, str, str | None]:
    """Merge repo/path args with GitHub tree URLs in ``repo`` or ``question``."""
    if (repo or "").strip():
        repo, path = _apply_tree_url(str(repo).strip(), path=path)

    parsed = parse_github_tree_url(question)
    if parsed:
        url_repo, url_path = parsed
        if not (repo or "").strip():
            repo = url_repo
        if not normalize_repo_path(path) and url_path:
            path = url_path
        cleaned = strip_github_urls(question)
        scoped_path = normalize_repo_path(path)
        if not cleaned:
            question = default_path_question(scoped_path or url_path or "this path")
        else:
            question = cleaned
    elif not (repo or "").strip():
        default_url = github_search_default_tree_url()
        if default_url:
            repo, path = _apply_tree_url(default_url, path=path)

    return (repo or None), question.strip(), normalize_repo_path(path)

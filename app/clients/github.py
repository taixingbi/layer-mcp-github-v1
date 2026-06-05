"""GitHub REST: README and code search."""

from __future__ import annotations

import base64
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import httpx

from app.clients.readme_cache import readme_cache_get, readme_cache_put
from app.config import CODE_HITS_MAX, README_MAX, SNIPPET_MAX


def github_token() -> str:
    """Return GitHub PAT from GITHUB_TOKEN or GITHUB_PERSONAL_ACCESS_TOKEN."""
    return (
        os.environ.get("GITHUB_TOKEN") or os.environ.get("GITHUB_PERSONAL_ACCESS_TOKEN") or ""
    ).strip()


def gh_headers() -> dict[str, str]:
    """Default GitHub REST headers including optional Bearer auth."""
    token = github_token()
    h = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def search_keywords(question: str) -> str:
    """Derive a short GitHub code-search query from the user question."""
    words = re.findall(r"[a-zA-Z_][a-zA-Z0-9_]{2,}", question or "")
    if words:
        return " ".join(words[:4])
    cleaned = re.sub(r"[^\w\s-]", " ", question or "")
    parts = [p for p in cleaned.split() if len(p) >= 2][:3]
    return " ".join(parts) if parts else "main"


def _decode_readme_payload(data: dict[str, Any]) -> str:
    content = data.get("content") or ""
    encoding = data.get("encoding") or "base64"
    if encoding == "base64" and content:
        raw = base64.b64decode(content).decode("utf-8", errors="replace")
        return raw[:README_MAX]
    return ""


def fetch_readme(client: httpx.Client, full_name: str) -> str:
    """Fetch README with in-process TTL cache (no network on cache hit)."""
    cached = readme_cache_get(full_name)
    if cached is not None:
        return cached.text

    owner, name = full_name.split("/", 1)
    r = client.get(
        f"https://api.github.com/repos/{owner}/{name}/readme",
        headers=gh_headers(),
    )
    if r.status_code == 404:
        readme_cache_put(full_name, "", r.headers.get("ETag"))
        return ""
    r.raise_for_status()
    text = _decode_readme_payload(r.json())
    readme_cache_put(full_name, text, r.headers.get("ETag"))
    return text


def _search_code(
    client: httpx.Client,
    query: str,
    per_page: int,
) -> list[dict[str, Any]]:
    """Run one GitHub code search; return raw API items (empty on 403/422)."""
    r = client.get(
        "https://api.github.com/search/code",
        params={"q": query, "per_page": per_page},
        headers={**gh_headers(), "Accept": "application/vnd.github.text-match+json"},
    )
    if r.status_code in (403, 422):
        return []
    r.raise_for_status()
    return r.json().get("items") or []


def _item_to_hit(item: dict[str, Any], default_repo: str) -> dict[str, str]:
    """Normalize one search API item to our hit dict."""
    path = item.get("path") or ""
    repo_full = (item.get("repository") or {}).get("full_name") or default_repo
    snippet = ""
    for tm in item.get("text_matches") or []:
        frag = tm.get("fragment") or ""
        if frag:
            snippet = frag.strip()[:SNIPPET_MAX]
            break
    return {
        "path": path,
        "url": item.get("html_url") or "",
        "snippet": snippet,
        "repo": repo_full,
    }


def github_fetch_workers() -> int:
    """Thread pool size for parallel GitHub REST calls."""
    return max(1, int(os.environ.get("GITHUB_FETCH_WORKERS", "8")))


def fetch_readmes_parallel(client: httpx.Client, full_names: list[str]) -> dict[str, str]:
    """Fetch READMEs concurrently."""
    if not full_names:
        return {}
    if len(full_names) == 1:
        fn = full_names[0]
        return {fn: fetch_readme(client, fn)}

    workers = min(github_fetch_workers(), len(full_names))
    out: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(fetch_readme, client, fn): fn for fn in full_names}
        for fut in as_completed(futures):
            fn = futures[fut]
            out[fn] = fut.result()
    return out


def fetch_code_hits_multi(
    client: httpx.Client,
    full_names: list[str],
    question: str,
    *,
    per_page: int = CODE_HITS_MAX,
) -> list[dict[str, str]]:
    """Code search per repo; parallel queries when multi-repo."""
    if not full_names:
        return []
    kw = search_keywords(question)

    if len(full_names) == 1:
        items = _search_code(client, f"{kw} repo:{full_names[0]}", per_page)
        return [_item_to_hit(item, full_names[0]) for item in items[:per_page]]

    per_repo = max(3, per_page // len(full_names))
    workers = min(github_fetch_workers(), len(full_names))

    def _search_one(fn: str) -> tuple[str, list[dict[str, Any]]]:
        return fn, _search_code(client, f"{kw} repo:{fn}", per_repo)

    repo_batches: list[tuple[str, list[dict[str, Any]]]] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(_search_one, fn) for fn in full_names]
        for fut in as_completed(futures):
            repo_batches.append(fut.result())

    items: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    order = {fn: idx for idx, fn in enumerate(full_names)}
    for fn, batch in sorted(repo_batches, key=lambda pair: order[pair[0]]):
        for item in batch:
            url = item.get("html_url") or ""
            if url and url in seen_urls:
                continue
            if url:
                seen_urls.add(url)
            items.append(item)
            if len(items) >= per_page:
                break
        if len(items) >= per_page:
            break

    return [_item_to_hit(item, full_names[0]) for item in items[:per_page]]

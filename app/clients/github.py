"""GitHub REST: README and code search."""

from __future__ import annotations

import base64
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, TypeVar

import httpx

from app.clients.readme_cache import readme_cache_get, readme_cache_put
from app.config import CODE_HITS_MAX, MULTI_REPO_CODE_HITS_MAX, README_MAX, SNIPPET_MAX

T = TypeVar("T")


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


def search_keywords(question: str, *, path_prefix: str | None = None) -> str:
    """Derive a short GitHub code-search query from the user question."""
    words = re.findall(r"[a-zA-Z_][a-zA-Z0-9_]{2,}", question or "")
    if words:
        return " ".join(words[:4])
    if path_prefix:
        parts = [p for p in path_prefix.strip("/").split("/") if len(p) >= 2]
        if parts:
            return " ".join(parts[-3:])
    cleaned = re.sub(r"[^\w\s-]", " ", question or "")
    parts = [p for p in cleaned.split() if len(p) >= 2][:3]
    return " ".join(parts) if parts else "main"


def _path_qualifier(path_prefix: str | None) -> str:
    path = (path_prefix or "").strip("/")
    return f" path:{path}" if path else ""


def _fetch_file_content(
    client: httpx.Client,
    owner: str,
    name: str,
    file_path: str,
) -> dict[str, str] | None:
    """Fetch one file from the contents API as a code hit."""
    response = client.get(
        f"https://api.github.com/repos/{owner}/{name}/contents/{file_path}",
        headers=gh_headers(),
    )
    if response.status_code != 200:
        return None
    data = response.json()
    if data.get("type") != "file":
        return None
    snippet = _decode_readme_payload(data)
    if not snippet:
        return None
    full_name = f"{owner}/{name}"
    return {
        "path": file_path,
        "url": data.get("html_url") or f"https://github.com/{full_name}/blob/HEAD/{file_path}",
        "snippet": snippet[: SNIPPET_MAX * 2],
        "repo": full_name,
    }


def fetch_path_files(
    client: httpx.Client,
    full_name: str,
    path_prefix: str,
    *,
    max_files: int = 8,
) -> list[dict[str, str]]:
    """Fetch key files under a directory path (e.g. Next.js blog pages)."""
    owner, name = full_name.split("/", 1)
    prefix = path_prefix.strip("/")
    response = client.get(
        f"https://api.github.com/repos/{owner}/{name}/contents/{prefix}",
        headers=gh_headers(),
    )
    if response.status_code == 404:
        return []
    response.raise_for_status()
    entries = response.json()
    if not isinstance(entries, list):
        entries = [entries]

    targets: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        entry_path = str(entry.get("path") or "")
        entry_type = str(entry.get("type") or "")
        if entry_type == "file":
            targets.append(entry_path)
        elif entry_type == "dir":
            targets.append(f"{entry_path}/page.tsx")

    for extra in (f"{prefix}/page.tsx", f"{prefix}/layout.tsx"):
        if extra not in targets:
            targets.insert(0, extra)

    slice_targets = targets[: min(len(targets), max(max_files * 2, max_files))]
    workers = min(github_fetch_workers(), max(1, len(slice_targets)))
    ordered: list[dict[str, str] | None] = [None] * len(slice_targets)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(_fetch_file_content, client, owner, name, file_path): idx
            for idx, file_path in enumerate(slice_targets)
        }
        for fut in as_completed(futures):
            idx = futures[fut]
            ordered[idx] = fut.result()

    hits: list[dict[str, str]] = []
    for hit in ordered:
        if hit:
            hits.append(hit)
        if len(hits) >= max_files:
            break
    return hits


def _merge_code_hits(*groups: list[dict[str, str]]) -> list[dict[str, str]]:
    merged: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    for group in groups:
        for hit in group:
            url = (hit.get("url") or "").strip()
            if url and url in seen_urls:
                continue
            if url:
                seen_urls.add(url)
            merged.append(hit)
    return merged


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
    if r.status_code in (401, 403, 422):
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
    path_prefix: str | None = None,
) -> list[dict[str, str]]:
    """Code search per repo; parallel queries when multi-repo."""
    if not full_names:
        return []
    kw = (
        search_keywords("", path_prefix=path_prefix)
        if path_prefix
        else search_keywords(question, path_prefix=path_prefix)
    )
    if path_prefix and kw == "main":
        kw = search_keywords(question, path_prefix=path_prefix)
    path_q = _path_qualifier(path_prefix)

    if len(full_names) == 1:
        items = _search_code(client, f"{kw}{path_q} repo:{full_names[0]}", per_page)
        return [_item_to_hit(item, full_names[0]) for item in items[:per_page]]

    per_repo = max(3, per_page // len(full_names))
    workers = min(github_fetch_workers(), len(full_names))

    def _search_one(fn: str) -> tuple[str, list[dict[str, Any]]]:
        return fn, _search_code(client, f"{kw}{path_q} repo:{fn}", per_repo)

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


def _timed_call(fn: Callable[..., T], /, *args: Any, **kwargs: Any) -> tuple[T, int]:
    """Run ``fn`` and return ``(result, duration_ms)``."""
    t0 = time.perf_counter()
    result = fn(*args, **kwargs)
    return result, int((time.perf_counter() - t0) * 1000)


def fetch_evidence_parallel(
    client: httpx.Client,
    full_names: list[str],
    question: str,
    *,
    multi: bool,
    path_prefix: str | None = None,
) -> tuple[dict[str, str], list[dict[str, str]], dict[str, int]]:
    """Fetch READMEs, code search, and optional path files concurrently."""
    latency: dict[str, int] = {}
    if not full_names:
        return {}, [], latency

    per_page = MULTI_REPO_CODE_HITS_MAX if multi else CODE_HITS_MAX
    path_scope = bool(path_prefix and len(full_names) == 1)
    workers = max(github_fetch_workers(), 3 if path_scope else 2)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        fut_readme = pool.submit(_timed_call, fetch_readmes_parallel, client, full_names)
        fut_code = pool.submit(
            _timed_call,
            fetch_code_hits_multi,
            client,
            full_names,
            question,
            per_page=per_page,
            path_prefix=path_prefix,
        )
        fut_path = None
        if path_scope:
            fut_path = pool.submit(
                _timed_call,
                fetch_path_files,
                client,
                full_names[0],
                path_prefix,
            )

        readmes, latency["github_readme"] = fut_readme.result()
        code_hits, code_ms = fut_code.result()
        if fut_path is not None:
            path_hits, path_ms = fut_path.result()
            code_hits = _merge_code_hits(path_hits, code_hits)
            latency["github_search"] = max(code_ms, path_ms)
        else:
            latency["github_search"] = code_ms

    return readmes, code_hits, latency

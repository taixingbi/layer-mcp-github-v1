"""Map layer-web-v1 ``app/blog`` source paths to public ``/blog/{slug}`` URLs."""

from __future__ import annotations

import re
from typing import Any

# Keep in sync with layer-web-v1 ``app/lib/blog-posts.ts`` slugs + display titles.
BLOG_POST_TITLES: dict[str, str] = {
    "building-an-ai-orchestrator": "Building an AI Orchestrator",
    "layer-gateway-inference-design": "Gateway Inference Design",
    "layer-rag-query-design": "Hybrid RAG in Production",
    "router-sft-dpo-training": "Training the HuntAI Router",
    "role-based-access-control": "Role-Based Access in HuntAI",
    "grafana-observability": "Grafana Observability",
}

_GITHUB_BLOG_BLOB_RE = re.compile(
    r"https://github\.com/[^/\s)]+/[^/\s)]+/blob/[^/\s)]+/app/blog/([^/\s)]+)/page\.tsx",
    re.IGNORECASE,
)


def blog_slug_from_path(path: str) -> str | None:
    """Extract blog slug from ``app/blog/{slug}/page.tsx`` (or similar)."""
    normalized = path.replace("\\", "/").strip("/")
    parts = normalized.split("/")
    if len(parts) < 3 or parts[0] != "app" or parts[1] != "blog":
        return None
    slug = parts[2]
    if slug in ("page.tsx", "layout.tsx"):
        return None
    return slug


def blog_post_path(slug: str) -> str:
    """Public site path for a blog article."""
    return f"/blog/{slug}"


def blog_post_title(slug: str) -> str:
    """Human-friendly documentation title for Learn More links."""
    return BLOG_POST_TITLES.get(slug, slug.replace("-", " ").title())


def citation_for_code_hit(hit: dict[str, str], *, full_name: str) -> dict[str, Any]:
    """Build one citation row for a code/path hit (blog paths → site URLs)."""
    repo = hit.get("repo") or full_name
    path = hit.get("path") or ""
    url = (hit.get("url") or "").strip()
    if not url and path:
        url = f"https://github.com/{repo}/blob/HEAD/{path}"

    slug = blog_slug_from_path(path)
    if slug:
        return {
            "url": blog_post_path(slug),
            "label": blog_post_title(slug),
            "repo": repo,
            "type": "blog",
            "path": path,
            "blog_slug": slug,
        }

    short = repo.split("/", 1)[-1] if "/" in repo else repo
    label = f"{short}/{path}" if path else path or url
    return {
        "url": url,
        "label": label,
        "repo": repo,
        "type": "code",
        "path": path,
    }


def rewrite_blog_urls_in_text(text: str) -> str:
    """Replace GitHub blob URLs for blog TSX sources with ``/blog/{slug}`` paths."""
    if not text or "app/blog" not in text:
        return text
    return _GITHUB_BLOG_BLOB_RE.sub(lambda m: blog_post_path(m.group(1)), text)

"""Blog path → public /blog URL mapping for github_search."""

from __future__ import annotations

from app.ask.blog_links import (
    blog_post_path,
    blog_post_title,
    blog_slug_from_path,
    citation_for_code_hit,
    rewrite_blog_urls_in_text,
)
from app.ask.citations import build_citations


def test_blog_slug_from_path():
    assert blog_slug_from_path("app/blog/building-an-ai-orchestrator/page.tsx") == (
        "building-an-ai-orchestrator"
    )
    assert blog_slug_from_path("app/blog/page.tsx") is None


def test_citation_for_code_hit_uses_blog_url():
    row = citation_for_code_hit(
        {
            "path": "app/blog/grafana-observability/page.tsx",
            "url": "https://github.com/taixingbi/layer-web-v1/blob/main/app/blog/grafana-observability/page.tsx",
            "repo": "taixingbi/layer-web-v1",
        },
        full_name="taixingbi/layer-web-v1",
    )
    assert row["type"] == "blog"
    assert row["url"] == "/blog/grafana-observability"
    assert row["label"] == "Grafana Observability"


def test_build_citations_blog_source_url():
    cites = build_citations(
        "taixingbi/layer-web-v1",
        "",
        [
            {
                "path": "app/blog/layer-gateway-inference-design/page.tsx",
                "url": "https://github.com/taixingbi/layer-web-v1/blob/main/app/blog/layer-gateway-inference-design/page.tsx",
            }
        ],
    )
    assert cites[0]["url"] == "/blog/layer-gateway-inference-design"
    assert cites[0]["label"] == "Gateway Inference Design"


def test_rewrite_blog_urls_in_text():
    raw = (
        "[Gateway Inference Design]"
        "(https://github.com/taixingbi/layer-web-v1/blob/main/app/blog/layer-gateway-inference-design/page.tsx)"
    )
    out = rewrite_blog_urls_in_text(raw)
    assert "/blog/layer-gateway-inference-design" in out
    assert "github.com" not in out


def test_blog_post_title_fallback():
    assert blog_post_title("building-an-ai-orchestrator") == "Building an AI Orchestrator"
    assert blog_post_path("foo-bar") == "/blog/foo-bar"

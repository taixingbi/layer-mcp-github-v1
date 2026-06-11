"""resolve_repos question routing integration."""

from __future__ import annotations

from app.allowlist.resolve import resolve_repos


def test_resolve_repos_routes_subset_from_question(monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_OWNER", "taixingbi")
    monkeypatch.setenv("GITHUB_REPO_ROUTING", "true")
    monkeypatch.setenv("GITHUB_ROUTE_MAX_REPOS", "5")

    out = resolve_repos(
        None,
        question="in huntai, what gateway for vllm design?",
    )

    assert out["ok"] is True
    assert len(out["full_names"]) <= 5
    assert len(out["full_names"]) >= 1
    assert any("gateway-inference" in fn for fn in out["full_names"])
    if len(out["full_names"]) == 1:
        assert out["scope"] == out["full_names"][0]
    else:
        assert out["scope"] == "routed"

"""Path scope and GitHub tree URL parsing."""

from app.ask.path_scope import (
    parse_github_tree_url,
    resolve_search_inputs,
    strip_github_urls,
)


def test_parse_github_tree_url() -> None:
    url = "https://github.com/taixingbi/layer-web-v1/tree/main/app/blog"
    parsed = parse_github_tree_url(url)
    assert parsed == ("layer-web-v1", "app/blog")


def test_resolve_search_inputs_from_url_only() -> None:
    repo, question, path = resolve_search_inputs(
        None,
        "https://github.com/taixingbi/layer-web-v1/tree/main/app/blog",
    )
    assert repo == "layer-web-v1"
    assert path == "app/blog"
    assert "app/blog" in question


def test_resolve_search_inputs_keeps_explicit_repo_and_path() -> None:
    repo, question, path = resolve_search_inputs(
        "layer-web-v1",
        "What posts exist?",
        "app/blog",
    )
    assert repo == "layer-web-v1"
    assert path == "app/blog"
    assert question == "What posts exist?"


def test_resolve_search_inputs_repo_tree_url() -> None:
    repo, question, path = resolve_search_inputs(
        "https://github.com/taixingbi/layer-web-v1/tree/main/app/blog",
        "introduce this huntAi project",
    )
    assert repo == "layer-web-v1"
    assert path == "app/blog"
    assert question == "introduce this huntAi project"


def test_resolve_search_inputs_defaults_when_repo_omitted(monkeypatch) -> None:
    monkeypatch.delenv("GITHUB_SEARCH_DEFAULT_TREE_URL", raising=False)
    repo, question, path = resolve_search_inputs(None, "introduce this huntAi project")
    assert repo == "layer-web-v1"
    assert path == "app/blog"
    assert question == "introduce this huntAi project"


def test_strip_github_urls() -> None:
    text = "see https://github.com/o/r/tree/main/foo/bar for details"
    assert strip_github_urls(text) == "see  for details"

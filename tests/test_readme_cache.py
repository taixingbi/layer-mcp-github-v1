"""README TTL cache and ETag handling."""

from __future__ import annotations

from unittest.mock import MagicMock

import httpx

from app.clients import readme_cache
from app.clients.github import fetch_readme


def test_fetch_readme_uses_cache_without_network(monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_README_CACHE_TTL_SEC", "3600")
    readme_cache._CACHE.clear()

    readme_cache.readme_cache_put("org/repo", "cached text", "etag-1")

    client = MagicMock(spec=httpx.Client)
    text = fetch_readme(client, "org/repo")

    assert text == "cached text"
    client.get.assert_not_called()


def test_fetch_readme_populates_cache_on_miss(monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_README_CACHE_TTL_SEC", "3600")
    readme_cache._CACHE.clear()

    response = MagicMock(
        status_code=200,
        headers={"ETag": "etag-1"},
    )
    response.json.return_value = {
        "content": "SGVsbG8=",
        "encoding": "base64",
    }
    client = MagicMock(spec=httpx.Client)
    client.get.return_value = response

    text = fetch_readme(client, "org/repo")

    assert text == "Hello"
    client.get.assert_called_once()
    assert fetch_readme(client, "org/repo") == "Hello"
    assert client.get.call_count == 1

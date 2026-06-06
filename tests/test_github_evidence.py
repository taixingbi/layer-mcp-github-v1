"""Parallel GitHub evidence fetch."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx

from app.clients.github import fetch_evidence_parallel


def test_fetch_evidence_parallel_runs_readme_and_code_together() -> None:
    client = httpx.Client()
    with (
        patch("app.clients.github.fetch_readmes_parallel") as mock_readme,
        patch("app.clients.github.fetch_code_hits_multi") as mock_code,
        patch("app.clients.github.fetch_path_files") as mock_path,
    ):
        mock_readme.return_value = {"taixingbi/foo": "readme text"}
        mock_code.return_value = [
            {"path": "a.py", "url": "https://github.com/x/a.py", "snippet": "x", "repo": "taixingbi/foo"}
        ]

        readmes, code_hits, latency = fetch_evidence_parallel(
            client,
            ["taixingbi/foo"],
            "how does routing work?",
            multi=False,
        )

    mock_readme.assert_called_once()
    mock_code.assert_called_once()
    mock_path.assert_not_called()
    assert readmes["taixingbi/foo"] == "readme text"
    assert len(code_hits) == 1
    assert "github_readme" in latency
    assert "github_search" in latency


def test_fetch_evidence_parallel_merges_path_hits() -> None:
    client = httpx.Client()
    with (
        patch("app.clients.github.fetch_readmes_parallel", return_value={"taixingbi/web": ""}),
        patch(
            "app.clients.github.fetch_code_hits_multi",
            return_value=[
                {
                    "path": "search.py",
                    "url": "https://github.com/t/web/search.py",
                    "snippet": "s",
                    "repo": "taixingbi/web",
                }
            ],
        ),
        patch(
            "app.clients.github.fetch_path_files",
            return_value=[
                {
                    "path": "app/blog/page.tsx",
                    "url": "https://github.com/t/web/app/blog/page.tsx",
                    "snippet": "blog",
                    "repo": "taixingbi/web",
                }
            ],
        ),
    ):
        _readmes, code_hits, latency = fetch_evidence_parallel(
            client,
            ["taixingbi/web"],
            "introduce blog",
            multi=False,
            path_prefix="app/blog",
        )

    urls = {h["url"] for h in code_hits}
    assert "https://github.com/t/web/app/blog/page.tsx" in urls
    assert "https://github.com/t/web/search.py" in urls
    assert latency["github_search"] >= 0


def test_fetch_path_files_fetches_in_parallel() -> None:
    from app.clients.github import fetch_path_files

    client = MagicMock()
    listing = MagicMock()
    listing.status_code = 200
    listing.json.return_value = [
        {"path": "app/blog/a.tsx", "type": "file"},
        {"path": "app/blog/b.tsx", "type": "file"},
    ]
    client.get.return_value = listing

    def _file_hit(_client, owner, name, file_path):
        return {
            "path": file_path,
            "url": f"https://github.com/{owner}/{name}/blob/{file_path}",
            "snippet": "x",
            "repo": f"{owner}/{name}",
        }

    with patch("app.clients.github._fetch_file_content", side_effect=_file_hit):
        hits = fetch_path_files(client, "taixingbi/web", "app/blog", max_files=2)

    assert len(hits) == 2
    assert all(h["snippet"] == "x" for h in hits)

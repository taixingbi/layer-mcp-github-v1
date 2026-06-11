"""Environment and constants."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent

README_MAX = 8000
CODE_HITS_MAX = 15
SNIPPET_MAX = 400
LLM_CONTEXT_README_MAX = 6000
MULTI_REPO_README_MAX = 800
MULTI_REPO_CODE_HITS_MAX = 12
# Cap user message size so prompts fit vLLM --max-model-len (2048) with max_tokens (512).
# Chars != tokens; keep conservative for code/README-heavy bodies + long system prompt.
LLM_USER_BODY_MAX_CHARS = 2400
# Default scoped search when ``repo`` is omitted (tree URL → repo + path).
GITHUB_SEARCH_DEFAULT_TREE_URL = (
    "https://github.com/taixingbi/layer-web-v1/tree/main/app/blog"
)


def llm_user_body_max_chars() -> int:
    """Max characters for the github_search LLM user message (sources + question)."""
    return int(os.environ.get("LLM_USER_BODY_MAX_CHARS", str(LLM_USER_BODY_MAX_CHARS)))

def multi_repo_code_hits_max() -> int:
    """Max code-search hits merged across repos for multi-repo github_search."""
    return int(os.environ.get("MULTI_REPO_CODE_HITS_MAX", str(MULTI_REPO_CODE_HITS_MAX)))

load_dotenv(ROOT / ".env")

HTTP_HOST = (os.environ.get("HTTP_HOST") or "127.0.0.1").strip()
HTTP_PORT = int(os.environ.get("HTTP_PORT", "8000"))
MCP_HTTP_PATH = "/v1/mcp"


def synth_engine() -> str:
    """Synthesis backend: legacy (LLM gateway) or cursor_sdk."""
    raw = (os.environ.get("SYNTH_ENGINE") or "legacy").strip().lower()
    return raw if raw in ("legacy", "cursor_sdk") else "legacy"


def cursor_api_key() -> str:
    return (os.environ.get("CURSOR_API_KEY") or "").strip()


def cursor_model() -> str:
    return (os.environ.get("CURSOR_MODEL") or "composer-2.5").strip()


def cursor_runtime_cwd() -> str:
    return (os.environ.get("CURSOR_RUNTIME_CWD") or "/tmp").strip()


def github_search_follow_ups() -> bool:
    """Second LLM pass for follow-up questions (off by default — saves ~1–3s latency)."""
    raw = (os.environ.get("GITHUB_SEARCH_FOLLOW_UPS") or "false").strip().lower()
    return raw in ("1", "true", "yes", "on")


def github_search_answer_format() -> str:
    """Answer shape: ``text`` (prose + [n] citations) or ``blocks`` (structured JSON)."""
    raw = (os.environ.get("GITHUB_SEARCH_ANSWER_FORMAT") or "text").strip().lower()
    return raw if raw in ("text", "blocks") else "text"


def github_search_default_tree_url() -> str:
    """Tree URL used when ``repo`` is omitted (parsed into repo short name + path)."""
    return (
        os.environ.get("GITHUB_SEARCH_DEFAULT_TREE_URL") or GITHUB_SEARCH_DEFAULT_TREE_URL
    ).strip()

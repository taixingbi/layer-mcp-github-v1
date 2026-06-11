"""Pytest hooks and stubs for optional third-party packages."""

from __future__ import annotations

import sys
from types import ModuleType
from unittest.mock import MagicMock


def _ensure_cursor_sdk_stub() -> None:
    """Allow @patch('cursor_sdk.*') without installing cursor-sdk in CI/dev."""
    if "cursor_sdk" in sys.modules:
        return
    mod = ModuleType("cursor_sdk")
    mod.Agent = MagicMock()
    mod.AgentOptions = MagicMock
    mod.LocalAgentOptions = MagicMock
    mod.CursorAgentError = type("CursorAgentError", (Exception,), {})
    sys.modules["cursor_sdk"] = mod


_ensure_cursor_sdk_stub()

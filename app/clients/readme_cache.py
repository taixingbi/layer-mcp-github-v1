"""In-process README cache with TTL and GitHub ETag revalidation."""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass

_CACHE: dict[str, "_Entry"] = {}
_LOCK = threading.Lock()


@dataclass
class _Entry:
    text: str
    etag: str | None
    expires_at: float


def readme_cache_ttl_sec() -> int:
    """Seconds to serve cached README without revalidation (0 disables cache)."""
    return max(0, int(os.environ.get("GITHUB_README_CACHE_TTL_SEC", "3600")))


def readme_cache_get(full_name: str) -> _Entry | None:
    """Return a fresh cache entry, or ``None`` if missing or expired."""
    ttl = readme_cache_ttl_sec()
    if ttl <= 0:
        return None
    now = time.monotonic()
    with _LOCK:
        entry = _CACHE.get(full_name)
        if entry is None or entry.expires_at <= now:
            if entry is not None:
                del _CACHE[full_name]
            return None
        return entry


def readme_cache_put(full_name: str, text: str, etag: str | None) -> None:
    """Store README text and optional ETag."""
    ttl = readme_cache_ttl_sec()
    if ttl <= 0:
        return
    with _LOCK:
        _CACHE[full_name] = _Entry(
            text=text,
            etag=(etag or "").strip() or None,
            expires_at=time.monotonic() + ttl,
        )


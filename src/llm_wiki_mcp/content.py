"""Shared content slicing helpers for bounded MCP responses."""

from __future__ import annotations

from typing import Any

DEFAULT_CONTENT_LIMIT = 50_000


def slice_content(content: str, offset: int = 0, limit: int = DEFAULT_CONTENT_LIMIT) -> dict[str, Any]:
    """Return a bounded text slice plus pagination metadata."""

    if offset < 0:
        raise ValueError("offset must be >= 0")
    if limit <= 0:
        raise ValueError("limit must be > 0")
    total = len(content)
    end = min(total, offset + limit)
    return {
        "content": content[offset:end],
        "offset": offset,
        "limit": limit,
        "total_chars": total,
        "truncated": end < total,
    }

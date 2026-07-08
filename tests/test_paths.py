from __future__ import annotations

from pathlib import Path

import pytest

from llm_wiki_mcp.paths import WikiPathError, WikiPaths


def test_resolve_rejects_parent_escape(sample_wiki: Path) -> None:
    paths = WikiPaths(sample_wiki)
    with pytest.raises(WikiPathError):
        paths.resolve("../outside.md")


def test_require_under_rejects_non_raw(sample_wiki: Path) -> None:
    paths = WikiPaths(sample_wiki)
    with pytest.raises(WikiPathError):
        paths.require_under("domains/agent/concepts/example.md", "raw")

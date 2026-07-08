from __future__ import annotations

from pathlib import Path

import pytest

from llm_wiki_mcp.paths import WikiPathError, WikiPaths


def test_resolve_rejects_parent_escape(sample_wiki: Path) -> None:
    paths = WikiPaths(sample_wiki)
    with pytest.raises(WikiPathError):
        paths.resolve("../outside.md")


def test_resolve_rejects_absolute_outside_root(
    sample_wiki: Path, tmp_path: Path
) -> None:
    outside = tmp_path / "outside.md"
    outside.write_text("outside")
    paths = WikiPaths(sample_wiki)
    with pytest.raises(WikiPathError):
        paths.resolve(outside)


def test_require_under_rejects_non_raw(sample_wiki: Path) -> None:
    paths = WikiPaths(sample_wiki)
    with pytest.raises(WikiPathError):
        paths.require_under("domains/agent/concepts/example.md", "raw")


def test_require_under_rejects_raw_parent_traversal(sample_wiki: Path) -> None:
    paths = WikiPaths(sample_wiki)
    with pytest.raises(WikiPathError):
        paths.require_under("raw/../domains/agent/concepts/example.md", "raw")

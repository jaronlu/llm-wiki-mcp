from __future__ import annotations

from pathlib import Path

import pytest

from llm_wiki_mcp.paths import WikiPathError, WikiPaths
from llm_wiki_mcp.sync import sync_domain_file


def test_sync_updates_existing_file_by_name_in_domain(sample_wiki: Path) -> None:
    paths = WikiPaths(sample_wiki)
    content = "# Updated\n\nReplacement content.\n"

    result = sync_domain_file(
        paths,
        fileName="example.md",
        content=content,
        domain="agent",
    )

    assert result["action"] == "updated"
    assert result["path"] == "domains/agent/concepts/example.md"
    assert result["would_write"] is True
    assert (sample_wiki / "domains/agent/concepts/example.md").read_text() == content


def test_sync_creates_missing_file_in_domain_default_type_dir(
    sample_wiki: Path,
) -> None:
    paths = WikiPaths(sample_wiki)
    content = "# New Page\n\nNew content.\n"

    result = sync_domain_file(
        paths,
        fileName="new-page",
        content=content,
        domain="agent",
    )

    assert result["action"] == "created"
    assert result["path"] == "domains/agent/concepts/new-page.md"
    assert (sample_wiki / "domains/agent/concepts/new-page.md").read_text() == content


def test_sync_updates_explicit_relative_path_in_domain(sample_wiki: Path) -> None:
    paths = WikiPaths(sample_wiki)
    reference = sample_wiki / "domains/agent/references/example.md"
    reference.parent.mkdir(parents=True)
    reference.write_text("# Old\n")

    result = sync_domain_file(
        paths,
        fileName="references/example.md",
        content="# New\n",
        domain="agent",
    )

    assert result["action"] == "updated"
    assert result["path"] == "domains/agent/references/example.md"
    assert reference.read_text() == "# New\n"


def test_sync_rejects_parent_traversal(sample_wiki: Path) -> None:
    with pytest.raises(WikiPathError):
        sync_domain_file(
            WikiPaths(sample_wiki),
            fileName="../outside.md",
            content="# Outside\n",
            domain="agent",
        )

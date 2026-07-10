from __future__ import annotations

from pathlib import Path

import pytest

from llm_wiki_mcp.paths import WikiPaths
from llm_wiki_mcp.raw import create_raw_source, read_raw_source


def test_read_raw_source(sample_wiki: Path) -> None:
    result = read_raw_source(WikiPaths(sample_wiki), "raw/10-AI/example.md")
    assert result["path"] == "raw/10-AI/example.md"
    assert result["immutable"] is True
    assert "LangGraph" in result["content"]


def test_read_raw_source_supports_size_cap(sample_wiki: Path) -> None:
    result = read_raw_source(
        WikiPaths(sample_wiki), "raw/10-AI/example.md", offset=2, limit=5
    )
    assert result["content"] == "Raw E"
    assert result["offset"] == 2
    assert result["limit"] == 5
    assert result["total_chars"] > 5
    assert result["truncated"] is True


def test_read_raw_source_accepts_workshop_raw_path(sample_wiki: Path) -> None:
    result = read_raw_source(
        WikiPaths(sample_wiki), "workshop/example-project/raw/design.md"
    )
    assert result["path"] == "workshop/example-project/raw/design.md"
    assert "Workshop raw evidence" in result["content"]


def test_create_raw_source_disallows_overwrite(sample_wiki: Path) -> None:
    paths = WikiPaths(sample_wiki)
    create_raw_source(paths, "raw/10-AI/new.md", "# New\n")
    assert (sample_wiki / "raw/10-AI/new.md").read_text() == "# New\n"
    with pytest.raises(FileExistsError):
        create_raw_source(paths, "raw/10-AI/new.md", "# Other\n")


def test_create_raw_source_accepts_workshop_raw_path(sample_wiki: Path) -> None:
    paths = WikiPaths(sample_wiki)
    result = create_raw_source(
        paths, "workshop/example-project/raw/new.md", "# New Workshop Source\n"
    )
    assert result["path"] == "workshop/example-project/raw/new.md"
    assert (sample_wiki / result["path"]).is_file()

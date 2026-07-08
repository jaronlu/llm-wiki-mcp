from __future__ import annotations

from pathlib import Path

from llm_wiki_mcp.pages import read_page
from llm_wiki_mcp.paths import WikiPaths
from llm_wiki_mcp.search import search_wiki


def test_read_page_parses_frontmatter_and_links(sample_wiki: Path) -> None:
    result = read_page(WikiPaths(sample_wiki), "domains/agent/concepts/example.md")
    assert result["frontmatter"]["title"] == "Example Page"
    assert result["frontmatter"]["type"] == "concept"
    assert result["wikilinks"] == ["domains/agent/concepts/other"]


def test_read_page_accepts_slug_without_md(sample_wiki: Path) -> None:
    result = read_page(WikiPaths(sample_wiki), "domains/agent/concepts/example")
    assert result["path"] == "domains/agent/concepts/example.md"


def test_read_page_supports_size_cap(sample_wiki: Path) -> None:
    result = read_page(WikiPaths(sample_wiki), "domains/agent/concepts/example", limit=10)
    assert len(result["content"]) == 10
    assert result["total_chars"] > 10
    assert result["truncated"] is True


def test_search_wiki_returns_metadata(sample_wiki: Path) -> None:
    result = search_wiki(WikiPaths(sample_wiki), "LangGraph", scope="formal", domain="agent")
    assert result["count"] == 1
    first = result["results"][0]
    assert first["path"] == "domains/agent/concepts/example.md"
    assert first["indexed"] is True

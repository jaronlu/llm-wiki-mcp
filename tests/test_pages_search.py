from __future__ import annotations

from pathlib import Path

from llm_wiki_mcp.pages import read_page
from llm_wiki_mcp.paths import WikiPaths
from llm_wiki_mcp.search import search_wiki


def test_read_page_parses_frontmatter_and_links(sample_wiki: Path) -> None:
    (sample_wiki / "domains/agent/concepts/backlink.md").write_text(
        "---\n"
        "title: Backlink Page\n"
        "created: 2026-01-01\n"
        "updated: 2026-01-01\n"
        "type: concept\n"
        "tags: [ai, agent]\n"
        "sources: [raw/10-AI/example.md]\n"
        "confidence: medium\n"
        "---\n\n"
        "# Backlink Page\n\nSee [[domains/agent/concepts/example]].\n"
    )
    result = read_page(WikiPaths(sample_wiki), "domains/agent/concepts/example.md")
    assert result["frontmatter"]["title"] == "Example Page"
    assert result["frontmatter"]["type"] == "concept"
    assert result["warnings"] == []
    assert result["wikilinks"] == ["domains/agent/concepts/other"]
    assert result["backlinks"] == ["domains/agent/concepts/backlink.md"]


def test_read_page_accepts_slug_without_md(sample_wiki: Path) -> None:
    result = read_page(WikiPaths(sample_wiki), "domains/agent/concepts/example")
    assert result["path"] == "domains/agent/concepts/example.md"


def test_read_page_accepts_workshop_entrypoint(sample_wiki: Path) -> None:
    result = read_page(WikiPaths(sample_wiki), "workshop/example-project/README")
    assert result["path"] == "workshop/example-project/README.md"
    assert result["frontmatter"]["type"] == "entity"


def test_read_page_supports_size_cap(sample_wiki: Path) -> None:
    result = read_page(
        WikiPaths(sample_wiki), "domains/agent/concepts/example", limit=10
    )
    assert len(result["content"]) == 10
    assert result["total_chars"] > 10
    assert result["truncated"] is True


def test_search_wiki_returns_metadata(sample_wiki: Path) -> None:
    result = search_wiki(
        WikiPaths(sample_wiki), "LangGraph", scope="formal", domain="agent"
    )
    assert result["count"] >= 1
    first = result["results"][0]
    assert first["path"] == "domains/agent/concepts/example.md"
    assert first["indexed"] is True
    assert first["score"] > 0


def test_search_wiki_long_query_uses_partial_ranked_matches(sample_wiki: Path) -> None:
    result = search_wiki(
        WikiPaths(sample_wiki),
        "LangGraph interrupt missing-term",
        scope="formal",
        domain="agent",
    )
    assert result["count"] == 1
    assert result["results"][0]["path"] == "domains/agent/concepts/example.md"


def test_search_wiki_matches_raw_source_path_tokens(sample_wiki: Path) -> None:
    result = search_wiki(WikiPaths(sample_wiki), "10-AI example", scope="raw")
    assert result["count"] >= 1
    assert result["next_action"] == "read_raw_source"
    assert "raw/10-AI/example.md" in [item["path"] for item in result["results"]]


def test_search_wiki_scope_all_prefers_formal_pages(sample_wiki: Path) -> None:
    result = search_wiki(WikiPaths(sample_wiki), "LangGraph raw source", scope="all")

    assert result["count"] >= 2
    assert result["next_action"] == "read_page"
    assert result["results"][0]["path"] == "domains/agent/concepts/example.md"
    assert "raw/10-AI/example.md" in [item["path"] for item in result["results"]]


def test_search_wiki_finds_workshop_entrypoint_as_formal(sample_wiki: Path) -> None:
    result = search_wiki(WikiPaths(sample_wiki), "Workshop MCP", scope="formal")
    assert result["count"] == 1
    assert result["next_action"] == "read_page"
    assert result["results"][0]["path"] == "workshop/example-project/README.md"

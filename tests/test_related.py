from __future__ import annotations

from pathlib import Path

from llm_wiki_mcp.related import find_related_pages
from llm_wiki_mcp.paths import WikiPaths


def test_find_related_pages_from_page_uses_tags_and_content(sample_wiki: Path) -> None:
    (sample_wiki / "domains/agent/concepts/interrupt.md").write_text(
        "---\n"
        "title: Interrupt Patterns\n"
        "created: 2026-01-01\n"
        "updated: 2026-01-01\n"
        "type: concept\n"
        "tags: [ai, agent]\n"
        "sources: [raw/10-AI/example.md]\n"
        "confidence: medium\n"
        "---\n\n"
        "# Interrupt Patterns\n\nLangGraph interrupt workflows.\n"
    )
    (sample_wiki / "domains/agent/concepts/unrelated.md").write_text(
        "---\n"
        "title: Prompt Style\n"
        "created: 2026-01-01\n"
        "updated: 2026-01-01\n"
        "type: concept\n"
        "tags: [writing]\n"
        "sources: [raw/10-AI/example.md]\n"
        "confidence: medium\n"
        "---\n\n"
        "# Prompt Style\n\nTone and editing.\n"
    )

    result = find_related_pages(WikiPaths(sample_wiki), page="domains/agent/concepts/example", limit=3)

    assert result["mode"] == "page"
    assert result["source_path"] == "domains/agent/concepts/example.md"
    assert result["count"] >= 1
    assert result["results"][0]["path"] == "domains/agent/concepts/interrupt.md"
    assert result["results"][0]["score"] > 0
    assert all(item["path"] != "domains/agent/concepts/example.md" for item in result["results"])


def test_find_related_pages_from_query_returns_scored_matches(sample_wiki: Path) -> None:
    (sample_wiki / "domains/agent/concepts/langgraph.md").write_text(
        "---\n"
        "title: LangGraph Memory\n"
        "created: 2026-01-01\n"
        "updated: 2026-01-01\n"
        "type: concept\n"
        "tags: [ai, agent]\n"
        "sources: [raw/10-AI/example.md]\n"
        "confidence: medium\n"
        "---\n\n"
        "# LangGraph Memory\n\nLangGraph agent memory patterns.\n"
    )

    result = find_related_pages(WikiPaths(sample_wiki), query="LangGraph memory", limit=2)

    assert result["mode"] == "query"
    assert result["query"] == "LangGraph memory"
    assert result["results"][0]["path"] == "domains/agent/concepts/langgraph.md"
    assert result["results"][0]["score"] > 0


def test_find_related_pages_rejects_oversized_limit(sample_wiki: Path) -> None:
    try:
        find_related_pages(WikiPaths(sample_wiki), query="LangGraph", limit=51)
    except ValueError as exc:
        assert "limit must be <= 50" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_find_related_pages_requires_page_or_query(sample_wiki: Path) -> None:
    try:
        find_related_pages(WikiPaths(sample_wiki))
    except ValueError as exc:
        assert "page or query" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_find_related_pages_skips_discovered_symlinks_outside_root(sample_wiki: Path, tmp_path: Path) -> None:
    outside = tmp_path / "outside.md"
    outside.write_text("# Outside\n\nLangGraph secret outside root.\n")
    symlink = sample_wiki / "domains/agent/concepts/outside.md"
    symlink.symlink_to(outside)

    result = find_related_pages(WikiPaths(sample_wiki), query="LangGraph", limit=10)

    assert all(item["path"] != "domains/agent/concepts/outside.md" for item in result["results"])

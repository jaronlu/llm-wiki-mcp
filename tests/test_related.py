from __future__ import annotations

from pathlib import Path

from llm_wiki_mcp.paths import WikiPaths
from llm_wiki_mcp.related import find_related_pages


def test_find_related_pages_from_topic_uses_domain_tags_and_content(
    sample_wiki: Path,
) -> None:
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

    result = find_related_pages(
        WikiPaths(sample_wiki), topic="LangGraph interrupt", domain="agent", limit=3
    )

    assert result["topic"] == "LangGraph interrupt"
    assert result["domain"] == "agent"
    assert result["count"] >= 1
    assert "domains/agent/concepts/interrupt.md" in {
        item["path"] for item in result["results"]
    }
    assert result["results"][0]["score"] > 0
    assert "reason" in result["results"][0]


def test_find_related_pages_from_topic_returns_scored_matches(
    sample_wiki: Path,
) -> None:
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

    result = find_related_pages(
        WikiPaths(sample_wiki), topic="LangGraph memory", limit=2
    )

    assert result["topic"] == "LangGraph memory"
    assert result["results"][0]["path"] == "domains/agent/concepts/langgraph.md"
    assert result["results"][0]["score"] > 0


def test_find_related_pages_rejects_oversized_limit(sample_wiki: Path) -> None:
    try:
        find_related_pages(WikiPaths(sample_wiki), topic="LangGraph", limit=51)
    except ValueError as exc:
        assert "limit must be <= 50" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_find_related_pages_requires_topic(sample_wiki: Path) -> None:
    try:
        find_related_pages(WikiPaths(sample_wiki), topic="")
    except ValueError as exc:
        assert "topic must not be empty" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_find_related_pages_skips_discovered_symlinks_outside_root(
    sample_wiki: Path, tmp_path: Path
) -> None:
    outside = tmp_path / "outside.md"
    outside.write_text("# Outside\n\nLangGraph secret outside root.\n")
    symlink = sample_wiki / "domains/agent/concepts/outside.md"
    symlink.symlink_to(outside)

    result = find_related_pages(WikiPaths(sample_wiki), topic="LangGraph", limit=10)

    assert all(
        item["path"] != "domains/agent/concepts/outside.md"
        for item in result["results"]
    )

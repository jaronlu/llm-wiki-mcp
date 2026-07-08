from __future__ import annotations

from pathlib import Path
from typing import Any

from llm_wiki_mcp.candidates import create_formal_page_candidate
from llm_wiki_mcp.frontmatter import validate_frontmatter
from llm_wiki_mcp.lint import run_lint
from llm_wiki_mcp.log import LogEntry, append_log
from llm_wiki_mcp.pages import read_page
from llm_wiki_mcp.paths import WikiPaths
from llm_wiki_mcp.raw import create_raw_source
from llm_wiki_mcp.search import search_wiki


def assert_response_envelope(result: dict[str, Any]) -> None:
    assert isinstance(result["candidate"], bool)
    assert isinstance(result["would_write"], bool)
    assert isinstance(result["warnings"], list)
    assert isinstance(result["errors"], list)
    assert isinstance(result["next_action"], str)


def test_candidate_response_envelope(sample_wiki: Path) -> None:
    result = create_formal_page_candidate(
        WikiPaths(sample_wiki),
        path="domains/agent/concepts/envelope.md",
        title="Envelope",
        page_type="concept",
        tags=["agent"],
        sources=["raw/10-AI/example.md"],
        confidence="medium",
        body="# Envelope\n",
    )

    assert_response_envelope(result)
    assert result["candidate"] is True
    assert result["would_write"] is False
    assert result["next_action"] == "review_candidate"


def test_write_response_envelope(sample_wiki: Path) -> None:
    paths = WikiPaths(sample_wiki)
    raw_result = create_raw_source(paths, "raw/10-AI/envelope.md", "# Envelope\n")
    log_result = append_log(
        paths,
        LogEntry(
            action="add",
            subject="envelope",
            reason="test",
            changes="new raw",
            impact="raw only",
            verification="unit test",
            entry_date="2026-07-08",
        ),
    )

    assert_response_envelope(raw_result)
    assert raw_result["would_write"] is True
    assert raw_result["next_action"] == "append_log"
    assert_response_envelope(log_result)
    assert log_result["would_write"] is True


def test_read_search_validation_and_lint_response_envelopes(sample_wiki: Path) -> None:
    paths = WikiPaths(sample_wiki)
    results = [
        read_page(paths, "domains/agent/concepts/example.md"),
        search_wiki(paths, "LangGraph", scope="formal"),
        validate_frontmatter(paths, "domains/agent/concepts/example.md"),
        run_lint(paths),
    ]

    for result in results:
        assert_response_envelope(result)
        assert result["candidate"] is False
        assert result["would_write"] is False

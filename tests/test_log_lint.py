from __future__ import annotations

from pathlib import Path

from llm_wiki_mcp.lint import run_lint
from llm_wiki_mcp.log import LogEntry, append_log
from llm_wiki_mcp.paths import WikiPaths


def test_append_log_adds_top_entry_and_trims(sample_wiki: Path) -> None:
    result = append_log(
        WikiPaths(sample_wiki),
        LogEntry(
            action="add",
            subject="new raw",
            reason="test",
            changes="new file",
            impact="raw only",
            verification="unit test",
            entry_date="2026-02-01",
        ),
        retention_entries=1,
    )
    text = (sample_wiki / "log.md").read_text()
    assert result["entry_count"] == 1
    assert result["trimmed_entries"] == 1
    assert "## [2026-02-01] add | new raw" in text
    assert "## [2026-01-01] add | old" not in text


def test_run_lint_returns_structured_summary(sample_wiki: Path) -> None:
    result = run_lint(WikiPaths(sample_wiki))
    assert result["exit_code"] == 0
    assert result["summary"]["formal_pages"] == 1
    assert result["errors"] == []

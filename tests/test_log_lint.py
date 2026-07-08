from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from llm_wiki_mcp.lint import run_lint
from llm_wiki_mcp.log import LogEntry, append_log, create_log_candidate
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


def test_create_log_candidate_renders_without_writing() -> None:
    result = create_log_candidate(
        action="add",
        subject="test page",
        reason="testing",
        changes="new page",
        impact="new only",
        verification="unit test",
        date="2026-07-08",
    )

    assert result["candidate"] is True
    assert result["would_write"] is False
    assert result["action"] == "add"
    assert result["subject"] == "test page"
    assert result["date"] == "2026-07-08"
    assert "## [2026-07-08] add | test page" in result["content"]


def test_run_lint_returns_structured_summary(sample_wiki: Path) -> None:
    result = run_lint(WikiPaths(sample_wiki), mode="full")
    assert result["exit_code"] == 0
    assert result["timed_out"] is False
    assert result["formal_pages"] == 1
    assert result["catalog_pages"] == 1
    assert result["summary"]["formal_pages"] == 1
    assert result["errors"] == []


def test_run_lint_timeout_is_structured(sample_wiki: Path) -> None:
    (sample_wiki / "scripts/wiki_lint.py").write_text("import time\ntime.sleep(1)\n")
    result = run_lint(WikiPaths(sample_wiki), timeout_seconds=0.01)
    assert result["exit_code"] is None
    assert result["timed_out"] is True
    assert "timed out" in result["errors"][0]


def test_run_lint_os_error_is_structured(tmp_path: Path) -> None:
    result = run_lint(WikiPaths(tmp_path / "missing-wiki"))
    assert result["exit_code"] is None
    assert result["timed_out"] is False
    assert "failed to run scripts/wiki_lint.py" in result["errors"][0]


def test_append_log_concurrent_writes_keep_all_entries(sample_wiki: Path) -> None:
    paths = WikiPaths(sample_wiki)

    def write_entry(index: int) -> None:
        append_log(
            paths,
            LogEntry(
                action="add",
                subject=f"entry {index}",
                reason="test",
                changes=f"entry {index}",
                impact="log only",
                verification="unit test",
                entry_date="2026-02-01",
            ),
            retention_entries=10,
        )

    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(write_entry, range(4)))

    text = (sample_wiki / "log.md").read_text()
    for index in range(4):
        assert f"## [2026-02-01] add | entry {index}" in text

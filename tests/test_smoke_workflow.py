from __future__ import annotations

from pathlib import Path

import pytest

from llm_wiki_mcp.bootstrap import init_wiki, inspect_wiki
from llm_wiki_mcp.candidates import (
    create_formal_page_candidate,
    update_index_candidate,
)
from llm_wiki_mcp.lint import run_lint
from llm_wiki_mcp.log import create_log_candidate
from llm_wiki_mcp.paths import WikiPaths
from llm_wiki_mcp.raw import create_raw_source, read_raw_source


def test_end_to_end_smoke_workflow(tmp_path: Path) -> None:
    root = tmp_path / "wiki"

    init_result = init_wiki(root, profile="personal", language="en")
    assert init_result["initialized"] is True
    assert "index.md" in init_result["created"]

    inspect_result = inspect_wiki(root)
    assert inspect_result["is_wiki"] is True
    assert inspect_result["next_action"] == "ready"

    paths = WikiPaths(root)
    raw_result = create_raw_source(
        paths, "raw/notes/example.md", "# Example\n\nA source."
    )
    assert raw_result["created"] is True
    assert read_raw_source(paths, "raw/notes/example.md")["immutable"] is True
    with pytest.raises(FileExistsError):
        create_raw_source(paths, "raw/notes/example.md", "# Overwrite")

    page_candidate = create_formal_page_candidate(
        paths,
        path="domains/agent/concepts/example.md",
        title="Example",
        page_type="concept",
        tags=["agent"],
        sources=["raw/notes/example.md"],
        confidence="medium",
        body="# Example\n\nCompiled candidate.",
        created="2026-07-08",
        updated="2026-07-08",
    )
    assert page_candidate["candidate"] is True
    assert page_candidate["would_write"] is False
    assert not (root / "domains/agent/concepts/example.md").exists()

    index_candidate = update_index_candidate(
        paths,
        page="domains/agent/concepts/example.md",
        title="Example",
        description="Compiled candidate",
        section_heading="Agent",
    )
    assert index_candidate["candidate"] is True
    assert index_candidate["would_write"] is False
    assert "[[domains/agent/concepts/example]]" in index_candidate["content"]

    log_candidate = create_log_candidate(
        action="add",
        subject="example candidate",
        reason="smoke test",
        changes="candidate only",
        impact="no write",
        verification="unit test",
        date="2026-07-08",
    )
    assert log_candidate["candidate"] is True
    assert log_candidate["would_write"] is False

    lint_result = run_lint(paths, mode="full")
    assert lint_result["exit_code"] == 0
    assert lint_result["errors"] == []

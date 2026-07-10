from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def sample_wiki(tmp_path: Path) -> Path:
    root = tmp_path / "wiki"
    (root / "domains/agent/concepts").mkdir(parents=True)
    (root / "raw/10-AI").mkdir(parents=True)
    (root / "workshop/example-project/raw").mkdir(parents=True)
    (root / "scripts").mkdir()
    (root / "index.md").write_text(
        "# Index\n\n- [[domains/agent/concepts/example]] — Example\n"
    )
    (root / "log.md").write_text(
        "# Wiki Log\n\n"
        "> Rolling recent log. Newest first.\n"
        "> Retention: latest 120 entries and max 1000 lines.\n"
        "> Full history lives in Git.\n\n"
        "## [2026-01-01] add | old\n"
        "- 原因: old\n"
    )
    (root / "domains/agent/concepts/example.md").write_text(
        "---\n"
        "title: Example Page\n"
        "created: 2026-01-01\n"
        "updated: 2026-01-01\n"
        "type: concept\n"
        "tags: [ai, agent]\n"
        "sources: [raw/10-AI/example.md]\n"
        "confidence: medium\n"
        "---\n\n"
        "# Example Page\n\nLangGraph interrupt and [[domains/agent/concepts/other]].\n"
    )
    (root / "raw/10-AI/example.md").write_text(
        "# Raw Example\n\nLangGraph raw source.\n"
    )
    (root / "workshop/example-project/README.md").write_text(
        "---\n"
        "title: Example Workshop Project\n"
        "created: 2026-01-01\n"
        "updated: 2026-01-01\n"
        "type: entity\n"
        "tags: [ai, agent]\n"
        "sources: [workshop/example-project/raw/design.md]\n"
        "confidence: medium\n"
        "---\n\n"
        "# Example Workshop Project\n\nWorkshop MCP project entry.\n"
    )
    (root / "workshop/example-project/raw/design.md").write_text(
        "# Workshop Design\n\nWorkshop raw evidence.\n"
    )
    (root / "scripts/wiki_lint.py").write_text(
        "print('Wiki lint summary')\n"
        "print('- formal pages: 1')\n"
        "print('- catalog pages: 1')\n"
        "print('- errors: 0')\n"
        "print('- warnings: 0')\n"
    )
    return root

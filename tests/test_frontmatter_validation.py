from __future__ import annotations

import json
from pathlib import Path

from llm_wiki_mcp.frontmatter import validate_frontmatter
from llm_wiki_mcp.pages import read_page
from llm_wiki_mcp.paths import WikiPaths


def test_validate_frontmatter_accepts_valid_formal_page(sample_wiki: Path) -> None:
    result = validate_frontmatter(
        WikiPaths(sample_wiki), "domains/agent/concepts/example"
    )

    assert result["valid"] is True
    assert result["path"] == "domains/agent/concepts/example.md"
    assert result["errors"] == []
    assert result["warnings"] == []


def test_validate_frontmatter_result_is_json_serializable(sample_wiki: Path) -> None:
    result = validate_frontmatter(
        WikiPaths(sample_wiki), "domains/agent/concepts/example"
    )

    json.dumps(result)
    assert result["frontmatter"]["created"] == "2026-01-01"
    assert result["frontmatter"]["updated"] == "2026-01-01"


def test_read_page_result_is_json_serializable(sample_wiki: Path) -> None:
    result = read_page(WikiPaths(sample_wiki), "domains/agent/concepts/example")

    json.dumps(result)
    assert result["frontmatter"]["created"] == "2026-01-01"
    assert result["frontmatter"]["updated"] == "2026-01-01"


def test_validate_frontmatter_reports_missing_and_invalid_fields(
    sample_wiki: Path,
) -> None:
    broken = sample_wiki / "domains/agent/concepts/broken.md"
    broken.write_text(
        "---\n"
        "title: Broken\n"
        "created: 2026-01-01\n"
        "updated: 2026-01-01\n"
        "type: invalid\n"
        "tags: ai\n"
        "confidence: certain\n"
        "---\n\n"
        "# Broken\n"
    )

    result = validate_frontmatter(
        WikiPaths(sample_wiki), "domains/agent/concepts/broken.md"
    )

    assert result["valid"] is False
    assert "missing required field: sources" in result["errors"]
    assert "invalid type: invalid" in result["errors"]
    assert "tags must be a list" in result["errors"]
    assert "invalid confidence: certain" in result["errors"]


def test_validate_frontmatter_reports_null_required_fields(sample_wiki: Path) -> None:
    broken = sample_wiki / "domains/agent/concepts/nulls.md"
    broken.write_text(
        "---\n"
        "title:\n"
        "created:\n"
        "updated:\n"
        "type: concept\n"
        "tags:\n"
        "sources:\n"
        "confidence: medium\n"
        "---\n\n"
        "# Nulls\n"
    )

    result = validate_frontmatter(
        WikiPaths(sample_wiki), "domains/agent/concepts/nulls.md"
    )

    assert result["valid"] is False
    assert "required field is empty: title" in result["errors"]
    assert "required field is empty: created" in result["errors"]
    assert "required field is empty: updated" in result["errors"]
    assert "required field is empty: tags" in result["errors"]
    assert "required field is empty: sources" in result["errors"]


def test_validate_frontmatter_reports_malformed_yaml(sample_wiki: Path) -> None:
    broken = sample_wiki / "domains/agent/concepts/malformed.md"
    broken.write_text("---\ntitle: [broken\n---\n\n# Malformed\n")

    result = validate_frontmatter(
        WikiPaths(sample_wiki), "domains/agent/concepts/malformed.md"
    )

    assert result["valid"] is False
    assert result["has_frontmatter"] is False
    assert any(
        error.startswith("invalid YAML frontmatter:") for error in result["errors"]
    )


def test_validate_frontmatter_uses_page_types_from_schema(sample_wiki: Path) -> None:
    (sample_wiki / "SCHEMA.md").write_text(
        "# Schema\n\n```yaml\n---\ntype: decision | concept\n---\n```\n"
    )
    page = sample_wiki / "domains/agent/concepts/decision.md"
    page.write_text(
        "---\n"
        "title: Decision\n"
        "created: 2026-01-01\n"
        "updated: 2026-01-01\n"
        "type: decision\n"
        "tags: [ai]\n"
        "sources: [raw/10-AI/example.md]\n"
        "confidence: medium\n"
        "---\n\n"
        "# Decision\n"
    )

    result = validate_frontmatter(
        WikiPaths(sample_wiki), "domains/agent/concepts/decision"
    )

    assert result["valid"] is True

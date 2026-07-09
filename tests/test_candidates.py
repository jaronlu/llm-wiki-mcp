from __future__ import annotations

from pathlib import Path

import yaml

from llm_wiki_mcp.candidates import (
    apply_candidate,
    compile_page,
    create_formal_page_candidate,
    create_update_candidate,
    load_candidate,
    update_index_candidate,
)
from llm_wiki_mcp.paths import WikiPaths


def test_create_formal_page_candidate_renders_markdown_without_writing(
    sample_wiki: Path,
) -> None:
    paths = WikiPaths(sample_wiki)

    result = create_formal_page_candidate(
        paths,
        path="domains/agent/concepts/new-concept.md",
        title="New Concept",
        page_type="concept",
        tags=["ai", "agent"],
        sources=["raw/10-AI/example.md"],
        confidence="medium",
        summary="A short reusable concept.",
        body="## 核心结论\n\n- Candidate only.\n",
        created="2026-07-08",
        updated="2026-07-08",
    )

    assert result["candidate"] is True
    assert result["would_write"] is False
    assert result["exists"] is False
    assert result["path"] == "domains/agent/concepts/new-concept.md"
    assert result["frontmatter"]["title"] == "New Concept"
    assert result["content"].startswith("---\ntitle: New Concept\n")
    assert "summary: A short reusable concept" in result["content"]
    assert "## 核心结论" in result["content"]
    assert not (sample_wiki / "domains/agent/concepts/new-concept.md").exists()


def test_create_formal_page_candidate_renders_yaml_safe_frontmatter(
    sample_wiki: Path,
) -> None:
    result = create_formal_page_candidate(
        WikiPaths(sample_wiki),
        path="domains/agent/concepts/yaml-safe.md",
        title="Agent: Tool",
        page_type="concept",
        tags=["ai: agent", "mcp,tool"],
        sources=["raw/10-AI/example: source.md"],
        confidence="medium",
        summary="Why: this matters",
        body="# Agent Tool\n",
        created="2026-07-08",
        updated="2026-07-08",
    )

    frontmatter_text = result["content"].split("---\n", 2)[1]
    frontmatter = yaml.safe_load(frontmatter_text)

    assert frontmatter["title"] == "Agent: Tool"
    assert frontmatter["summary"] == "Why: this matters"
    assert frontmatter["tags"] == ["ai: agent", "mcp,tool"]
    assert frontmatter["sources"] == ["raw/10-AI/example: source.md"]


def test_create_formal_page_candidate_rejects_existing_page(sample_wiki: Path) -> None:
    try:
        create_formal_page_candidate(
            WikiPaths(sample_wiki),
            path="domains/agent/concepts/example.md",
            title="Example Page",
            page_type="concept",
            tags=["ai"],
            sources=["raw/10-AI/example.md"],
            confidence="medium",
            body="# Example\n",
        )
    except FileExistsError as exc:
        assert "formal page already exists" in str(exc)
    else:
        raise AssertionError("expected FileExistsError")


def test_create_formal_page_candidate_rejects_raw_source_path(
    sample_wiki: Path,
) -> None:
    try:
        create_formal_page_candidate(
            WikiPaths(sample_wiki),
            path="raw/10-AI/not-formal.md",
            title="Bad",
            page_type="concept",
            tags=["ai"],
            sources=["raw/10-AI/example.md"],
            confidence="medium",
            body="# Bad\n",
        )
    except ValueError as exc:
        assert "formal page candidate must be under configured formal_dirs" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_create_formal_page_candidate_uses_page_types_from_schema(
    sample_wiki: Path,
) -> None:
    (sample_wiki / "SCHEMA.md").write_text(
        "# Schema\n\n```yaml\n---\ntype: decision | concept\n---\n```\n"
    )

    result = create_formal_page_candidate(
        WikiPaths(sample_wiki),
        path="domains/agent/concepts/decision.md",
        title="Decision",
        page_type="decision",
        tags=["ai"],
        sources=["raw/10-AI/example.md"],
        confidence="medium",
        body="# Decision\n",
    )

    assert result["frontmatter"]["type"] == "decision"


def test_update_index_candidate_inserts_link_under_existing_heading_without_writing(
    sample_wiki: Path,
) -> None:
    index_path = sample_wiki / "index.md"
    index_path.write_text(
        "# Index\n\n## Agent\n\n- [[domains/agent/concepts/example]] — Example\n"
    )

    result = update_index_candidate(
        WikiPaths(sample_wiki),
        page="domains/agent/concepts/new-concept.md",
        title="New Concept",
        description="Reusable MCP concept",
        section_heading="Agent",
    )

    assert result["candidate"] is True
    assert result["would_write"] is False
    assert result["already_indexed"] is False
    assert result["inserted"] is True
    assert (
        result["entry"]
        == "- [[domains/agent/concepts/new-concept]] — Reusable MCP concept"
    )
    assert (
        "- [[domains/agent/concepts/new-concept]] — Reusable MCP concept"
        in result["content"]
    )
    assert "new-concept" not in index_path.read_text()


def test_update_index_candidate_matches_nested_heading_text(sample_wiki: Path) -> None:
    index_path = sample_wiki / "index.md"
    index_path.write_text(
        "# Index\n\n"
        "## Agent\n\n"
        "### References\n\n"
        "- [[domains/agent/references/example-reference]] — Example reference\n\n"
        "### Summaries\n\n"
        "- [[domains/agent/summaries/example-summary]] — Example summary\n"
    )

    result = update_index_candidate(
        WikiPaths(sample_wiki),
        page="domains/agent/references/new-reference.md",
        title="New Reference",
        description="Reusable MCP reference",
        section_heading="References",
    )

    new_entry = "- [[domains/agent/references/new-reference]] — Reusable MCP reference"
    assert result["inserted"] is True
    assert result["content"].count("### References") == 1
    assert "\n## References\n" not in result["content"]
    assert result["content"].index(new_entry) < result["content"].index("### Summaries")


def test_update_index_candidate_detects_alias_and_anchor_links(
    sample_wiki: Path,
) -> None:
    index_path = sample_wiki / "index.md"
    index_path.write_text(
        "# Index\n\n"
        "## Agent\n\n"
        "- [[domains/agent/concepts/alias-page|Alias Page]] — Alias\n"
        "- [[domains/agent/concepts/anchor-page#Section]] — Anchor\n"
    )

    alias_result = update_index_candidate(
        WikiPaths(sample_wiki),
        page="domains/agent/concepts/alias-page.md",
        title="Alias Page",
        description="Alias",
        section_heading="Agent",
    )
    anchor_result = update_index_candidate(
        WikiPaths(sample_wiki),
        page="domains/agent/concepts/anchor-page.md",
        title="Anchor Page",
        description="Anchor",
        section_heading="Agent",
    )

    assert alias_result["already_indexed"] is True
    assert alias_result["inserted"] is False
    assert anchor_result["already_indexed"] is True
    assert anchor_result["inserted"] is False


def test_update_index_candidate_detects_existing_link(sample_wiki: Path) -> None:
    result = update_index_candidate(
        WikiPaths(sample_wiki),
        page="domains/agent/concepts/example.md",
        title="Example Page",
        description="Example",
        section_heading="Agent",
    )

    assert result["already_indexed"] is True
    assert result["inserted"] is False
    assert result["content"] == (sample_wiki / "index.md").read_text()


def test_create_update_candidate_returns_candidate_without_writing(
    sample_wiki: Path,
) -> None:
    result = create_update_candidate(
        WikiPaths(sample_wiki),
        page="domains/agent/concepts/example.md",
        title="Example Page",
        source="raw/10-AI/example.md",
        instruction="Add rerank vs hybrid search comparison",
        new_sections=["## Rerank vs Hybrid Search\n\n- Rerank: ...\n- Hybrid: ..."],
        new_sources=["raw/10-AI/new-source.md"],
        new_wikilinks=["domains/agent/concepts/rag-principles"],
    )

    assert result["candidate"] is True
    assert result["would_write"] is False
    assert result["page"] == "domains/agent/concepts/example.md"
    assert result["title"] == "Example Page"
    assert result["source"] == "raw/10-AI/example.md"
    assert result["instruction"] == "Add rerank vs hybrid search comparison"
    assert "Rerank vs Hybrid Search" in result["suggested_sections"][0]
    assert result["suggested_sources"] == ["raw/10-AI/new-source.md"]
    assert result["suggested_wikilinks"] == ["domains/agent/concepts/rag-principles"]
    assert result["reason_for_update"] is not None


def test_create_update_candidate_rejects_nonexistent_page(sample_wiki: Path) -> None:
    try:
        create_update_candidate(
            WikiPaths(sample_wiki),
            page="domains/agent/concepts/nonexistent.md",
            title="Missing",
        )
    except FileNotFoundError as exc:
        assert "target page not found" in str(exc)
    else:
        raise AssertionError("expected FileNotFoundError")


def test_compile_page_persists_candidate_bundle_and_apply_writes_atomically(
    sample_wiki: Path,
) -> None:
    paths = WikiPaths(sample_wiki)

    candidate = compile_page(
        paths,
        source="raw/10-AI/example.md",
        topic="Raw Example Formal",
        domain="agent",
        tags=["ai", "agent"],
    )
    cached = load_candidate(paths, candidate["candidate_id"])
    applied = apply_candidate(
        paths,
        candidate["candidate_id"],
        approved=True,
        expected_status="approved",
    )

    assert cached["status"] == "pending_review"
    assert cached["bundle"]["content_hash"] == candidate["bundle"]["content_hash"]
    assert cached["bundle"]["ops"][0]["op"] == "write_formal_page"
    assert applied["transaction"] == {"atomic": True, "rolled_back": False}
    assert (sample_wiki / "domains/agent/concepts/raw-example-formal.md").is_file()
    assert "raw-example-formal" in (sample_wiki / "index.md").read_text()
    assert "compile | domains/agent/concepts/raw-example-formal.md" in (
        sample_wiki / "log.md"
    ).read_text()
    assert (sample_wiki / ".llm-wiki/source-manifest.json").is_file()


def test_apply_candidate_rejects_stale_base_hash(sample_wiki: Path) -> None:
    paths = WikiPaths(sample_wiki)
    candidate = compile_page(
        paths,
        source="raw/10-AI/example.md",
        topic="Stale Candidate",
        domain="agent",
    )
    (sample_wiki / "index.md").write_text("# Changed\n")

    try:
        apply_candidate(paths, candidate["candidate_id"], approved=True)
    except RuntimeError as exc:
        assert "STALE_CANDIDATE: index.md" in str(exc)
    else:
        raise AssertionError("expected stale candidate rejection")

    assert load_candidate(paths, candidate["candidate_id"])["status"] == "stale"

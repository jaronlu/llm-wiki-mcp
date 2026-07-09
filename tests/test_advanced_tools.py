from __future__ import annotations

from pathlib import Path

from llm_wiki_mcp.advanced import (
    classify_source_candidate,
    compile_raw_to_formal_draft,
    detect_new_source,
    find_low_confidence_pages,
    find_referencing_pages,
    find_uncompiled_sources,
    knowledge_health_review,
    semantic_search,
    suggest_wikilinks,
    update_source_manifest,
    validate_public_safety,
    write_public_draft,
)
from llm_wiki_mcp.paths import WikiPaths


def test_semantic_search_returns_chunk_metadata(sample_wiki: Path) -> None:
    result = semantic_search(
        WikiPaths(sample_wiki), query="LangGraph interrupt", scope="formal"
    )

    assert result["embedding"] == "local-token-vector"
    assert result["count"] >= 1
    assert result["results"][0]["path"] == "domains/agent/concepts/example.md"
    assert "content" in result["results"][0]


def test_semantic_search_scope_all_prefers_formal_pages(sample_wiki: Path) -> None:
    result = semantic_search(
        WikiPaths(sample_wiki), query="LangGraph raw source", scope="all"
    )

    assert result["count"] == 2
    assert result["next_action"] == "read_page"
    assert result["results"][0]["path"] == "domains/agent/concepts/example.md"
    assert result["results"][1]["path"] == "raw/10-AI/example.md"


def test_semantic_search_raw_scope_points_to_raw_reader(sample_wiki: Path) -> None:
    result = semantic_search(
        WikiPaths(sample_wiki), query="LangGraph raw source", scope="raw"
    )

    assert result["count"] == 1
    assert result["next_action"] == "read_raw_source"
    assert result["results"][0]["path"] == "raw/10-AI/example.md"


def test_compile_raw_to_formal_draft_is_candidate_only(sample_wiki: Path) -> None:
    result = compile_raw_to_formal_draft(
        WikiPaths(sample_wiki),
        source="raw/10-AI/example.md",
        topic="LangGraph Runtime",
        domain="agent",
        tags=["ai", "agent"],
    )

    assert result["candidate"] is True
    assert result["would_write"] is False
    assert result["source"] == "raw/10-AI/example.md"
    assert result["decision"] in {"new_page", "update_existing"}
    assert result["frontmatter"]["sources"] == ["raw/10-AI/example.md"]
    assert not (sample_wiki / result["path"]).exists()


def test_classify_source_candidate_prefers_existing_page_when_related(
    sample_wiki: Path,
) -> None:
    result = classify_source_candidate(
        WikiPaths(sample_wiki),
        source="raw/10-AI/example.md",
        intent="LangGraph interrupt",
        domain="agent",
    )

    assert result["classification"] == "update_existing"
    assert result["next_action"] == "create_update_candidate"
    assert result["related_pages"]


def test_classify_source_candidate_can_ignore_empty_source(sample_wiki: Path) -> None:
    (sample_wiki / "raw/10-AI/empty.md").write_text("")

    result = classify_source_candidate(
        WikiPaths(sample_wiki), source="raw/10-AI/empty.md"
    )

    assert result["classification"] == "ignore"
    assert result["next_action"] == "no_action"


def test_public_draft_cleans_wikilinks_and_reports_safety(sample_wiki: Path) -> None:
    page = sample_wiki / "domains/agent/concepts/public.md"
    page.write_text(
        "---\n"
        "title: Public Page\n"
        "created: 2026-01-01\n"
        "updated: 2026-01-01\n"
        "type: concept\n"
        "tags: [ai]\n"
        "sources: [raw/10-AI/example.md]\n"
        "confidence: medium\n"
        "---\n\n"
        "# Public Page\n\nSee [[domains/agent/concepts/example|Example]].\n"
        "tok" + "en = abc123\n"
    )

    result = write_public_draft(
        WikiPaths(sample_wiki), "domains/agent/concepts/public.md"
    )

    assert result["candidate"] is True
    assert result["would_publish"] is False
    assert "---" not in result["content"]
    assert "[[" not in result["content"]
    assert "[REDACTED]" in result["content"]
    assert result["safety"]["safe"] is True


def test_validate_public_safety_flags_sensitive_content(sample_wiki: Path) -> None:
    result = validate_public_safety(
        WikiPaths(sample_wiki),
        content="tok" + "en = abc\n" + "/Users/" + "example/private",
    )

    assert result["safe"] is False
    assert {issue["kind"] for issue in result["issues"]} >= {"secret", "private_path"}


def test_source_manifest_detects_and_updates_raw_sources(sample_wiki: Path) -> None:
    paths = WikiPaths(sample_wiki)

    before = detect_new_source(paths, source="raw/10-AI/example.md")
    update = update_source_manifest(paths, sources=["raw/10-AI/example.md"])
    after = detect_new_source(paths, source="raw/10-AI/example.md")

    assert before["changes"][0]["status"] == "new"
    assert before["changes"][0]["suggested_action"] == "create_update_candidate"
    assert before["changes"][0]["suggested_actions"] == [
        {
            "action": "create_update_candidate",
            "source": "raw/10-AI/example.md",
            "page": "domains/agent/concepts/example.md",
            "title": "Example Page",
        }
    ]
    assert update["path"] == ".llm-wiki/source-manifest.json"
    assert (sample_wiki / ".llm-wiki/source-manifest.json").is_file()
    assert after["changes"] == []


def test_detect_new_source_suggests_formal_page_candidate_for_unreferenced_source(
    sample_wiki: Path,
) -> None:
    paths = WikiPaths(sample_wiki)
    (sample_wiki / "raw/10-AI/unreferenced.md").write_text("# New Source\n")

    result = detect_new_source(paths, source="raw/10-AI/unreferenced.md")

    assert result["changes"][0]["suggested_action"] == "create_formal_page_candidate"
    assert result["changes"][0]["suggested_actions"] == [
        {
            "action": "create_formal_page_candidate",
            "source": "raw/10-AI/unreferenced.md",
        }
    ]


def test_detect_new_source_returns_one_update_action_per_referencing_page(
    sample_wiki: Path,
) -> None:
    paths = WikiPaths(sample_wiki)
    second_page = sample_wiki / "domains/agent/concepts/second.md"
    second_page.write_text(
        "---\n"
        "title: Second Page\n"
        "created: 2026-01-01\n"
        "updated: 2026-01-01\n"
        "type: concept\n"
        "tags: [ai]\n"
        "sources: [raw/10-AI/example.md]\n"
        "confidence: medium\n"
        "---\n\n"
        "# Second Page\n\nAnother formal page using the same source.\n"
    )

    result = detect_new_source(paths, source="raw/10-AI/example.md")

    actions = result["changes"][0]["suggested_actions"]
    assert [action["page"] for action in actions] == [
        "domains/agent/concepts/example.md",
        "domains/agent/concepts/second.md",
    ]
    assert all(action["action"] == "create_update_candidate" for action in actions)


def test_find_referencing_and_uncompiled_sources(sample_wiki: Path) -> None:
    (sample_wiki / "raw/10-AI/uncompiled.md").write_text("# Uncompiled\n")

    references = find_referencing_pages(WikiPaths(sample_wiki), "raw/10-AI/example.md")
    new_page_target = find_referencing_pages(
        WikiPaths(sample_wiki), "raw/10-AI/uncompiled.md"
    )
    uncompiled = find_uncompiled_sources(WikiPaths(sample_wiki))

    assert references["count"] == 1
    assert references["pages"][0]["path"] == "domains/agent/concepts/example.md"
    assert new_page_target["next_action"] == "create_formal_page_candidate"
    assert "raw/10-AI/uncompiled.md" in uncompiled["sources"]


def test_suggest_wikilinks_and_health_review(sample_wiki: Path) -> None:
    low = sample_wiki / "domains/agent/concepts/low.md"
    low.write_text(
        "---\n"
        "title: Low Confidence\n"
        "created: 2024-01-01\n"
        "updated: 2024-01-01\n"
        "type: concept\n"
        "tags: [ai]\n"
        "sources: [raw/10-AI/example.md]\n"
        "confidence: low\n"
        "---\n\n"
        "# Low Confidence\n\nDeprecated LangGraph note.\n"
    )

    suggestions = suggest_wikilinks(WikiPaths(sample_wiki), text="LangGraph interrupt")
    low_confidence = find_low_confidence_pages(WikiPaths(sample_wiki))
    health = knowledge_health_review(WikiPaths(sample_wiki))

    assert (
        suggestions["suggestions"][0]["wikilink"]
        == "[[domains/agent/concepts/example]]"
    )
    assert low_confidence["pages"][0]["path"] == "domains/agent/concepts/low.md"
    assert "lint" in health
    assert "uncompiled_sources" in health

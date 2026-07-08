from __future__ import annotations

from pathlib import Path
import re

import pytest

from llm_wiki_mcp.server import mcp


@pytest.mark.anyio("asyncio")
async def test_all_tools_are_registered() -> None:
    tools = await mcp.list_tools()
    names = {tool.name for tool in tools}

    assert "search_wiki" in names
    assert "init_wiki" in names
    assert "inspect_wiki" in names
    assert "read_page" in names
    assert "read_raw_source" in names
    assert "create_raw_source" in names
    assert "append_log" in names
    assert "validate_frontmatter" in names
    assert "find_related_pages" in names
    assert "create_formal_page_candidate" in names
    assert "update_index_candidate" in names
    assert "create_update_candidate" in names
    assert "create_log_candidate" in names
    assert "run_lint" in names
    assert "semantic_search" in names
    assert "compile_raw_to_formal_draft" in names
    assert "write_public_draft" in names
    assert "validate_public_safety" in names
    assert "classify_source_candidate" in names
    assert "suggest_wikilinks" in names
    assert "detect_new_source" in names
    assert "find_referencing_pages" in names
    assert "update_source_manifest" in names
    assert "find_uncompiled_sources" in names
    assert "find_duplicate_topics" in names
    assert "find_stale_pages" in names
    assert "find_low_confidence_pages" in names
    assert "suggest_merge_candidates" in names
    assert "knowledge_health_review" in names
    assert "audit_wiki_structure" in names
    assert "standardize_page_candidate" in names


@pytest.mark.anyio("asyncio")
async def test_readme_tool_list_matches_registered_tools() -> None:
    tools = await mcp.list_tools()
    registered = {tool.name for tool in tools}
    readme = (Path(__file__).resolve().parents[1] / "README.md").read_text()
    tool_section = readme.split("## MCP tools", 1)[1].split("## Development", 1)[0]
    documented = set(re.findall(r"^- `([a-z_]+)`", tool_section, flags=re.MULTILINE))

    assert documented
    assert documented <= registered


@pytest.mark.anyio("asyncio")
async def test_tool_schemas_match_design_parameter_names() -> None:
    tools = {tool.name: tool for tool in await mcp.list_tools()}

    assert "type" in tools["search_wiki"].inputSchema["properties"]
    assert "page_type" not in tools["search_wiki"].inputSchema["properties"]
    assert "date" in tools["append_log"].inputSchema["properties"]
    assert "entry_date" not in tools["append_log"].inputSchema["properties"]
    assert set(tools["find_related_pages"].inputSchema["properties"]) == {
        "topic",
        "domain",
        "limit",
    }
    assert "mode" in tools["run_lint"].inputSchema["properties"]
    assert "page" in tools["write_public_draft"].inputSchema["properties"]
    assert set(tools["find_referencing_pages"].inputSchema["properties"]) == {"source"}
    assert "sources" in tools["update_source_manifest"].inputSchema["properties"]

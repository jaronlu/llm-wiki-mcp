from __future__ import annotations

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


@pytest.mark.anyio("asyncio")
async def test_tool_schemas_match_design_parameter_names() -> None:
    tools = {tool.name: tool for tool in await mcp.list_tools()}

    assert "type" in tools["search_wiki"].inputSchema["properties"]
    assert "page_type" not in tools["search_wiki"].inputSchema["properties"]
    assert "date" in tools["append_log"].inputSchema["properties"]
    assert "entry_date" not in tools["append_log"].inputSchema["properties"]
    assert set(tools["find_related_pages"].inputSchema["properties"]) == {"topic", "domain", "limit"}
    assert "mode" in tools["run_lint"].inputSchema["properties"]

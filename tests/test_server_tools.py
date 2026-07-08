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

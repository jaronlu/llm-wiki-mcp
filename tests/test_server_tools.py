from __future__ import annotations

import pytest

from llm_wiki_mcp.server import mcp


@pytest.mark.anyio("asyncio")
async def test_p1_tools_are_registered() -> None:
    tools = await mcp.list_tools()
    names = {tool.name for tool in tools}

    assert "find_related_pages" in names
    assert "validate_frontmatter" in names

from __future__ import annotations

import re
from pathlib import Path

import pytest

from llm_wiki_mcp.server import mcp


@pytest.mark.anyio("asyncio")
async def test_all_tools_are_registered() -> None:
    tools = await mcp.list_tools()
    names = {tool.name for tool in tools}

    assert names == {
        "init_wiki",
        "inspect_wiki",
        "search_wiki",
        "read_page",
        "read_raw_source",
        "create_raw_source",
        "append_log",
        "compile_page",
        "create_update_candidate",
        "apply_candidate",
        "run_lint",
        "knowledge_health_review",
        "write_public_draft",
        "validate_public_safety",
    }


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
    assert "mode" in tools["search_wiki"].inputSchema["properties"]
    assert "date" in tools["append_log"].inputSchema["properties"]
    assert "entry_date" not in tools["append_log"].inputSchema["properties"]
    assert "source" in tools["compile_page"].inputSchema["properties"]
    assert "candidate_id" in tools["apply_candidate"].inputSchema["properties"]
    assert "approved" in tools["apply_candidate"].inputSchema["properties"]
    assert "mode" in tools["run_lint"].inputSchema["properties"]
    assert "page" in tools["write_public_draft"].inputSchema["properties"]


@pytest.mark.anyio("asyncio")
async def test_registered_tools_return_public_response_envelope() -> None:
    _, payload = await mcp.call_tool("inspect_wiki", {})

    assert set(payload) == {"success", "data", "warnings", "error", "meta"}
    assert payload["success"] is True
    assert isinstance(payload["warnings"], list)
    assert payload["error"] is None
    assert "tool_version" in payload["meta"]

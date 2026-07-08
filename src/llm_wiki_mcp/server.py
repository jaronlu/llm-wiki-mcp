from __future__ import annotations

from typing import Any, Literal

from mcp.server.fastmcp import FastMCP

from .config import load_config
from .lint import run_lint as run_wiki_lint
from .log import LogEntry, append_log as append_wiki_log
from .pages import read_page as read_wiki_page
from .paths import WikiPaths
from .raw import create_raw_source as create_wiki_raw_source
from .raw import read_raw_source as read_wiki_raw_source
from .search import search_wiki as search_wiki_impl

config = load_config()
paths = WikiPaths(config.wiki_root)
mcp = FastMCP("llm-wiki-mcp")


@mcp.tool(description="Search llm-wiki formal pages and/or raw sources with wiki metadata.")
def search_wiki(
    query: str,
    scope: Literal["formal", "raw", "all"] = "formal",
    domain: str | None = None,
    page_type: str = "any",
    limit: int = 20,
) -> dict[str, Any]:
    return search_wiki_impl(paths, query=query, scope=scope, domain=domain, page_type=page_type, limit=limit)


@mcp.tool(description="Read a formal llm-wiki page and return frontmatter, content, and wikilinks.")
def read_page(page: str, offset: int = 0, limit: int = 50_000) -> dict[str, Any]:
    return read_wiki_page(paths, page, offset=offset, limit=limit)


@mcp.tool(description="Read an immutable raw source under raw/.")
def read_raw_source(path: str, offset: int = 0, limit: int = 50_000) -> dict[str, Any]:
    return read_wiki_raw_source(paths, path, offset=offset, limit=limit)


@mcp.tool(description="Create a new raw source under raw/. Existing files are never overwritten.")
def create_raw_source(path: str, content: str) -> dict[str, Any]:
    if not config.allow_write_raw:
        raise PermissionError("Raw source writes are disabled by config")
    return create_wiki_raw_source(paths, path=path, content=content)


@mcp.tool(description="Append a structured entry to log.md and trim old entries to retention.")
def append_log(
    action: str,
    subject: str,
    reason: str,
    changes: str,
    impact: str,
    verification: str,
    entry_date: str | None = None,
) -> dict[str, Any]:
    entry = LogEntry(
        action=action,
        subject=subject,
        reason=reason,
        changes=changes,
        impact=impact,
        verification=verification,
        entry_date=entry_date,
    )
    return append_wiki_log(paths, entry, retention_entries=config.log_retention_entries)


@mcp.tool(description="Run python3 scripts/wiki_lint.py and return structured lint results.")
def run_lint(timeout_seconds: float = 60.0) -> dict[str, Any]:
    return run_wiki_lint(paths, timeout_seconds=timeout_seconds)


def main() -> None:
    mcp.run("stdio")

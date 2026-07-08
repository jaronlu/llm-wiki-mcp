"""MCP tool registration and stdio server entrypoint."""

from __future__ import annotations

from typing import Any, Literal

from mcp.server.fastmcp import FastMCP

from .candidates import create_formal_page_candidate as create_wiki_formal_page_candidate
from .candidates import update_index_candidate as update_wiki_index_candidate
from .config import load_config
from .lint import run_lint as run_wiki_lint
from .log import LogEntry, append_log as append_wiki_log
from .frontmatter import validate_frontmatter as validate_wiki_frontmatter
from .pages import read_page as read_wiki_page
from .paths import WikiPaths
from .raw import create_raw_source as create_wiki_raw_source
from .raw import read_raw_source as read_wiki_raw_source
from .related import find_related_pages as find_related_wiki_pages
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
    """Search formal pages and/or raw sources and return structured metadata."""

    return search_wiki_impl(paths, query=query, scope=scope, domain=domain, page_type=page_type, limit=limit)


@mcp.tool(description="Read a formal llm-wiki page and return frontmatter, content, and wikilinks.")
def read_page(page: str, offset: int = 0, limit: int = 50_000) -> dict[str, Any]:
    """Read a formal wiki page or slug with bounded content output."""

    return read_wiki_page(paths, page, offset=offset, limit=limit)


@mcp.tool(description="Read an immutable raw source under raw/.")
def read_raw_source(path: str, offset: int = 0, limit: int = 50_000) -> dict[str, Any]:
    """Read a raw source under raw/ without exposing mutation capabilities."""

    return read_wiki_raw_source(paths, path, offset=offset, limit=limit)


@mcp.tool(description="Create a new raw source under raw/. Existing files are never overwritten.")
def create_raw_source(path: str, content: str) -> dict[str, Any]:
    """Create a new raw source using create-only filesystem semantics."""

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
    """Append a structured log.md entry using the repository log format."""

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


@mcp.tool(description="Validate a formal wiki page's YAML frontmatter shape.")
def validate_frontmatter(page: str) -> dict[str, Any]:
    """Validate required frontmatter fields for a formal wiki page or slug."""

    return validate_wiki_frontmatter(paths, page)


@mcp.tool(description="Find formal wiki pages related to a page or free-text query.")
def find_related_pages(
    page: str | None = None,
    query: str | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    """Find metadata-rich related formal pages using lightweight local scoring."""

    return find_related_wiki_pages(paths, page=page, query=query, limit=limit)


@mcp.tool(description="Render a formal page markdown candidate without writing it.")
def create_formal_page_candidate(
    path: str,
    title: str,
    page_type: str,
    tags: list[str],
    sources: list[str],
    confidence: str,
    body: str,
    summary: str | None = None,
    created: str | None = None,
    updated: str | None = None,
) -> dict[str, Any]:
    """Create a candidate formal wiki page for caller review, not disk write."""

    return create_wiki_formal_page_candidate(
        paths,
        path=path,
        title=title,
        page_type=page_type,
        tags=tags,
        sources=sources,
        confidence=confidence,
        body=body,
        summary=summary,
        created=created,
        updated=updated,
    )


@mcp.tool(description="Render an index.md update candidate without writing it.")
def update_index_candidate(page: str, title: str, description: str, section_heading: str) -> dict[str, Any]:
    """Create a candidate index.md update for caller review, not disk write."""

    return update_wiki_index_candidate(
        paths,
        page=page,
        title=title,
        description=description,
        section_heading=section_heading,
    )


@mcp.tool(description="Run python3 scripts/wiki_lint.py and return structured lint results.")
def run_lint(timeout_seconds: float = 60.0) -> dict[str, Any]:
    """Run the wiki lint script with a timeout and structured error output."""

    return run_wiki_lint(paths, timeout_seconds=timeout_seconds)


def main() -> None:
    """Start the llm-wiki MCP server over stdio transport."""

    mcp.run("stdio")

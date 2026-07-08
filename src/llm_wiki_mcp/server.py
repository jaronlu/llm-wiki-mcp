"""MCP tool registration and stdio server entrypoint."""

from __future__ import annotations

from typing import Any, Literal

from mcp.server.fastmcp import FastMCP

from . import (
    advanced,
    bootstrap,
    candidates,
    frontmatter,
    lint,
    pages,
    raw,
    related,
    search,
)
from . import log as log_tools
from .config import load_config
from .paths import WikiPaths

config = load_config()
paths = WikiPaths(
    config.wiki_root,
    formal_dirs=config.formal_dirs,
    raw_dirs=config.raw_dirs,
    non_formal_dirs=config.non_formal_dirs,
)
mcp = FastMCP("llm-wiki-mcp")


@mcp.tool(
    description="Initialize a minimal Karpathy-style LLM Wiki structure without overwriting by default."
)
def init_wiki(
    root: str | None = None, profile: str = "personal", language: str = "zh"
) -> dict[str, Any]:
    """Create missing llm-wiki files/directories for a new wiki root."""

    target_root = root or str(config.init_wiki_root or paths.root)
    return bootstrap.init_wiki(
        target_root,
        profile=profile,
        language=language,
        formal_dirs=config.formal_dirs,
        raw_dirs=config.raw_dirs,
        non_formal_dirs=config.non_formal_dirs,
    )


@mcp.tool(description="Inspect whether a directory has the minimal llm-wiki structure.")
def inspect_wiki(root: str | None = None) -> dict[str, Any]:
    """Inspect a wiki root without mutating files."""

    return bootstrap.inspect_wiki(
        root or str(paths.root),
        formal_dirs=config.formal_dirs,
        raw_dirs=config.raw_dirs,
        non_formal_dirs=config.non_formal_dirs,
    )


@mcp.tool(
    description="Search llm-wiki formal pages and/or raw sources with wiki metadata."
)
def search_wiki(
    query: str,
    scope: Literal["formal", "raw", "all"] = "formal",
    domain: str | None = None,
    type: str = "any",
    limit: int = 20,
) -> dict[str, Any]:
    """Search formal pages and/or raw sources and return structured metadata."""

    return search.search_wiki(
        paths, query=query, scope=scope, domain=domain, page_type=type, limit=limit
    )


@mcp.tool(
    description="Read a formal llm-wiki page and return frontmatter, content, and wikilinks."
)
def read_page(page: str, offset: int = 0, limit: int = 50_000) -> dict[str, Any]:
    """Read a formal wiki page or slug with bounded content output."""

    return pages.read_page(paths, page, offset=offset, limit=limit)


@mcp.tool(description="Read an immutable raw source under raw/.")
def read_raw_source(path: str, offset: int = 0, limit: int = 50_000) -> dict[str, Any]:
    """Read a raw source under raw/ without exposing mutation capabilities."""

    return raw.read_raw_source(paths, path, offset=offset, limit=limit)


@mcp.tool(
    description="Create a new raw source under raw/. Existing files are never overwritten."
)
def create_raw_source(path: str, content: str) -> dict[str, Any]:
    """Create a new raw source using create-only filesystem semantics."""

    if not config.allow_write_raw:
        raise PermissionError("Raw source writes are disabled by config")
    return raw.create_raw_source(paths, path=path, content=content)


@mcp.tool(
    description="Append a structured entry to log.md and trim old entries to retention."
)
def append_log(
    action: str,
    subject: str,
    reason: str,
    changes: str,
    impact: str,
    verification: str,
    date: str | None = None,
) -> dict[str, Any]:
    """Append a structured log.md entry using the repository log format."""

    entry = log_tools.LogEntry(
        action=action,
        subject=subject,
        reason=reason,
        changes=changes,
        impact=impact,
        verification=verification,
        entry_date=date,
    )
    return log_tools.append_log(
        paths, entry, retention_entries=config.log_retention_entries
    )


@mcp.tool(description="Validate a formal wiki page's YAML frontmatter shape.")
def validate_frontmatter(page: str) -> dict[str, Any]:
    """Validate required frontmatter fields for a formal wiki page or slug."""

    return frontmatter.validate_frontmatter(paths, page)


@mcp.tool(description="Find formal wiki pages related to a topic and optional domain.")
def find_related_pages(
    topic: str,
    domain: str | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    """Find metadata-rich related formal pages using lightweight local scoring."""

    return related.find_related_pages(paths, topic=topic, domain=domain, limit=limit)


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

    return candidates.create_formal_page_candidate(
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
def update_index_candidate(
    page: str, title: str, description: str, section_heading: str
) -> dict[str, Any]:
    """Create a candidate index.md update for caller review, not disk write."""

    return candidates.update_index_candidate(
        paths,
        page=page,
        title=title,
        description=description,
        section_heading=section_heading,
    )


@mcp.tool(
    description="Render an update candidate for an existing formal page without writing it."
)
def create_update_candidate(
    page: str,
    title: str,
    source: str | None = None,
    instruction: str | None = None,
    new_sections: list[str] | None = None,
    new_sources: list[str] | None = None,
    new_wikilinks: list[str] | None = None,
    reason_for_update: str | None = None,
) -> dict[str, Any]:
    """Generate an update candidate for an existing formal wiki page — not a new page."""

    return candidates.create_update_candidate(
        paths,
        page=page,
        title=title,
        source=source,
        instruction=instruction,
        new_sections=new_sections,
        new_sources=new_sources,
        new_wikilinks=new_wikilinks,
        reason_for_update=reason_for_update,
    )


@mcp.tool(description="Render a log.md entry candidate without writing it.")
def create_log_candidate(
    action: str,
    subject: str,
    reason: str,
    changes: str,
    impact: str,
    verification: str,
    date: str | None = None,
) -> dict[str, Any]:
    """Generate a log.md entry candidate for caller review, not disk write."""

    return log_tools.create_log_candidate(
        action=action,
        subject=subject,
        reason=reason,
        changes=changes,
        impact=impact,
        verification=verification,
        date=date,
    )


@mcp.tool(
    description="Run python3 scripts/wiki_lint.py and return structured lint results."
)
def run_lint(mode: str = "full", timeout_seconds: float = 60.0) -> dict[str, Any]:
    """Run the wiki lint script with a timeout and structured error output."""

    return lint.run_lint(paths, mode=mode, timeout_seconds=timeout_seconds)


@mcp.tool(
    description="Search wiki chunks using the local deterministic retrieval baseline."
)
def semantic_search(
    query: str,
    scope: Literal["formal", "raw", "all"] = "formal",
    limit: int = 10,
    chunk_chars: int = 1200,
) -> dict[str, Any]:
    """Return chunk-level metadata for formal/raw retrieval."""

    return advanced.semantic_search(
        paths, query=query, scope=scope, limit=limit, chunk_chars=chunk_chars
    )


@mcp.tool(
    description="Classify a raw source into raw, draft, formal candidate, update existing, or ignore workflow."
)
def classify_source_candidate(
    source: str, intent: str | None = None, domain: str | None = None
) -> dict[str, Any]:
    """Classify source lifecycle routing without mutating wiki files."""

    return advanced.classify_source_candidate(
        paths, source=source, intent=intent, domain=domain
    )


@mcp.tool(
    description="Compile a raw source into a formal page draft candidate without writing it."
)
def compile_raw_to_formal_draft(
    source: str,
    topic: str | None = None,
    domain: str = "general",
    page_type: str = "concept",
    tags: list[str] | None = None,
    confidence: str = "medium",
) -> dict[str, Any]:
    """Create a reviewable formal-page draft from one raw source."""

    return advanced.compile_raw_to_formal_draft(
        paths,
        source=source,
        topic=topic,
        domain=domain,
        page_type=page_type,
        tags=tags,
        confidence=confidence,
    )


@mcp.tool(
    description="Suggest Obsidian wikilinks for candidate content without editing files."
)
def suggest_wikilinks(
    text: str, limit: int = 10, domain: str | None = None
) -> dict[str, Any]:
    """Suggest related formal-page wikilinks for text."""

    return advanced.suggest_wikilinks(paths, text=text, limit=limit, domain=domain)


@mcp.tool(
    description="Render a public-site markdown draft candidate without publishing it."
)
def write_public_draft(
    page: str, title: str | None = None, redact: bool = True
) -> dict[str, Any]:
    """Clean frontmatter/wikilinks and return a public draft candidate."""

    return advanced.write_public_draft(paths, page=page, title=title, redact=redact)


@mcp.tool(description="Validate public-site candidate content for sensitive material.")
def validate_public_safety(
    content: str | None = None, page: str | None = None
) -> dict[str, Any]:
    """Check public content or a formal page for safety issues."""

    return advanced.validate_public_safety(paths, content=content, page=page)


@mcp.tool(
    description="Detect raw sources that are new or changed since the sidecar source manifest."
)
def detect_new_source(source: str | None = None) -> dict[str, Any]:
    """Detect changed raw sources and affected formal pages."""

    return advanced.detect_new_source(paths, source=source)


@mcp.tool(
    description="Find formal pages that reference a raw source in frontmatter.sources."
)
def find_referencing_pages(source: str) -> dict[str, Any]:
    """Locate formal pages affected by a raw source."""

    return advanced.find_referencing_pages(paths, source=source)


@mcp.tool(
    description="Update the sidecar raw source digest manifest without changing page frontmatter."
)
def update_source_manifest(sources: list[str] | None = None) -> dict[str, Any]:
    """Write .llm-wiki/source-manifest.json for incremental source detection."""

    return advanced.update_source_manifest(paths, sources=sources)


@mcp.tool(description="Find raw sources not referenced by any formal page.")
def find_uncompiled_sources() -> dict[str, Any]:
    """Find raw materials that have not been compiled into formal pages."""

    return advanced.find_uncompiled_sources(paths)


@mcp.tool(description="Find possibly duplicated formal topics using local similarity.")
def find_duplicate_topics(threshold: float = 0.55, limit: int = 20) -> dict[str, Any]:
    """Find overlapping formal pages for review."""

    return advanced.find_duplicate_topics(paths, threshold=threshold, limit=limit)


@mcp.tool(description="Find stale or deprecated-looking formal pages.")
def find_stale_pages(older_than_days: int = 365, limit: int = 20) -> dict[str, Any]:
    """Find pages with stale updated dates or deprecated API markers."""

    return advanced.find_stale_pages(
        paths, older_than_days=older_than_days, limit=limit
    )


@mcp.tool(description="Find formal pages marked confidence: low.")
def find_low_confidence_pages(limit: int = 20) -> dict[str, Any]:
    """Find pages that need stronger evidence."""

    return advanced.find_low_confidence_pages(paths, limit=limit)


@mcp.tool(description="Suggest merge candidates without deleting or rewriting pages.")
def suggest_merge_candidates(
    threshold: float = 0.65, limit: int = 10
) -> dict[str, Any]:
    """Suggest duplicate-topic merge candidates."""

    return advanced.suggest_merge_candidates(paths, threshold=threshold, limit=limit)


@mcp.tool(
    description="Summarize wiki health across lint, sources, duplicates, stale pages, and confidence."
)
def knowledge_health_review() -> dict[str, Any]:
    """Return a long-term governance health report."""

    return advanced.knowledge_health_review(paths)


@mcp.tool(
    description="Audit wiki structure and return standardization recommendations without writing."
)
def audit_wiki_structure() -> dict[str, Any]:
    """Inspect structure beyond the minimal inspect_wiki result."""

    return advanced.audit_wiki_structure(paths)


@mcp.tool(
    description="Render a frontmatter-standardized markdown candidate without writing."
)
def standardize_page_candidate(
    page: str, page_type: str = "concept", confidence: str = "low"
) -> dict[str, Any]:
    """Create a standardization candidate for an existing markdown page."""

    return advanced.standardize_page_candidate(
        paths, page=page, page_type=page_type, confidence=confidence
    )


def main() -> None:
    """Start the llm-wiki MCP server over stdio transport."""

    mcp.run("stdio")

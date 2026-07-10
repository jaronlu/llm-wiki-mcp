"""MCP tool registration and stdio server entrypoint."""

from __future__ import annotations

from typing import Any, Callable, Literal

from mcp.server.fastmcp import FastMCP

from . import advanced, bootstrap, candidates, lint, log, pages, raw, search
from .config import load_config
from .paths import WikiPathError, WikiPaths
from .responses import public_error, public_success, start_timer

config = load_config()
paths = WikiPaths(
    config.wiki_root,
    formal_dirs=config.formal_dirs,
    raw_dirs=config.raw_dirs,
    workshop_dirs=config.workshop_dirs,
    non_formal_dirs=config.non_formal_dirs,
)
mcp = FastMCP("llm-wiki-mcp")


def _error_code(exc: Exception) -> str:
    """Map internal exceptions to the public Tool Specification error model."""

    message = str(exc)
    if isinstance(exc, PermissionError):
        return "WRITE_DISABLED" if "disabled" in message else "PERMISSION_DENIED"
    if isinstance(exc, FileExistsError):
        return "FILE_ALREADY_EXISTS"
    if isinstance(exc, FileNotFoundError):
        return "PAGE_NOT_FOUND" if "page" in message.lower() else "SOURCE_NOT_FOUND"
    if isinstance(exc, WikiPathError):
        if "escapes wiki root" in message:
            return "OUT_OF_ROOT"
        return "INVALID_PATH"
    if "STALE_CANDIDATE" in message:
        return "STALE_CANDIDATE"
    if "APPLY_CONFLICT" in message:
        return "APPLY_CONFLICT"
    if isinstance(exc, ValueError):
        return "INVALID_ARGUMENT"
    return "INTERNAL_ERROR"


def _public_call(
    func: Callable[[], dict[str, Any]], request_id: str | None = None
) -> dict[str, Any]:
    """Run a tool implementation and wrap it in the public response envelope."""

    started_at = start_timer()
    try:
        data = func()
    except Exception as exc:  # noqa: BLE001 - public tools must not leak tracebacks.
        return public_error(
            _error_code(exc),
            str(exc),
            request_id=request_id,
            started_at=started_at,
        )
    warnings = data.pop("warnings", []) if isinstance(data.get("warnings"), list) else []
    data.pop("errors", None)
    return public_success(
        data,
        request_id=request_id,
        warnings=warnings,
        started_at=started_at,
    )


@mcp.tool(
    description="Initialize a minimal Karpathy-style LLM Wiki structure without overwriting by default."
)
def init_wiki(
    root: str | None = None,
    profile: str = "personal",
    language: str = "zh",
    request_id: str | None = None,
) -> dict[str, Any]:
    """Create missing llm-wiki files/directories for a new wiki root."""

    def run() -> dict[str, Any]:
        target_root = root or str(paths.root)
        return bootstrap.init_wiki(
            target_root,
            profile=profile,
            language=language,
            formal_dirs=config.formal_dirs,
            raw_dirs=config.raw_dirs,
            workshop_dirs=config.workshop_dirs,
            non_formal_dirs=config.non_formal_dirs,
        )

    return _public_call(run, request_id)


@mcp.tool(description="Inspect whether a directory has the minimal llm-wiki structure.")
def inspect_wiki(
    root: str | None = None, request_id: str | None = None
) -> dict[str, Any]:
    """Inspect a wiki root without mutating files."""

    return _public_call(
        lambda: bootstrap.inspect_wiki(
            root or str(paths.root),
            formal_dirs=config.formal_dirs,
            raw_dirs=config.raw_dirs,
            workshop_dirs=config.workshop_dirs,
            non_formal_dirs=config.non_formal_dirs,
        ),
        request_id,
    )


@mcp.tool(description="Search llm-wiki formal pages and/or raw sources with wiki metadata.")
def search_wiki(
    query: str,
    scope: Literal["formal", "raw", "all"] = "formal",
    mode: Literal["auto", "keyword", "semantic", "hybrid"] = "auto",
    domain: str | None = None,
    type: str = "any",
    limit: int = 20,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Search formal pages and/or raw sources and return structured metadata."""

    def run() -> dict[str, Any]:
        if mode in {"semantic", "hybrid"}:
            return advanced.semantic_search(
                paths, query=query, scope=scope, limit=limit
            )
        return search.search_wiki(
            paths, query=query, scope=scope, domain=domain, page_type=type, limit=limit
        )

    return _public_call(run, request_id)


@mcp.tool(description="Read a formal llm-wiki page and return wiki metadata.")
def read_page(
    page: str,
    offset: int = 0,
    limit: int = 50_000,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Read a formal wiki page or slug with bounded content output."""

    return _public_call(
        lambda: pages.read_page(paths, page, offset=offset, limit=limit), request_id
    )


@mcp.tool(description="Read an evidence-preserving raw source under raw/.")
def read_raw_source(
    path: str,
    offset: int = 0,
    limit: int = 50_000,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Read a raw source under raw/ without exposing mutation capabilities."""

    return _public_call(
        lambda: raw.read_raw_source(paths, path, offset=offset, limit=limit), request_id
    )


@mcp.tool(description="Create a new raw source under raw/. Existing files are never overwritten.")
def create_raw_source(
    path: str, content: str, request_id: str | None = None
) -> dict[str, Any]:
    """Create a new raw source using create-only filesystem semantics."""

    def run() -> dict[str, Any]:
        if not config.allow_write_raw:
            raise PermissionError("Raw source writes are disabled by config")
        return raw.create_raw_source(paths, path=path, content=content)

    return _public_call(run, request_id)


@mcp.tool(description="Append a structured entry to log.md and trim old entries to retention.")
def append_log(
    action: str,
    subject: str,
    reason: str,
    changes: str,
    impact: str,
    verification: str,
    date: str | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Append a structured log.md entry using the repository log format."""

    def run() -> dict[str, Any]:
        entry = log.LogEntry(
            action=action,
            subject=subject,
            reason=reason,
            changes=changes,
            impact=impact,
            verification=verification,
            entry_date=date,
        )
        return log.append_log(
            paths, entry, retention_entries=config.log_retention_entries
        )

    return _public_call(run, request_id)


@mcp.tool(description="Compile a raw source into a persisted formal page Candidate.")
def compile_page(
    source: str,
    topic: str | None = None,
    domain: str = "general",
    page_type: str = "concept",
    tags: list[str] | None = None,
    confidence: str = "medium",
    request_id: str | None = None,
) -> dict[str, Any]:
    """Compile raw evidence into a reviewable Candidate bundle."""

    return _public_call(
        lambda: candidates.compile_page(
            paths,
            source=source,
            topic=topic,
            domain=domain,
            page_type=page_type,
            tags=tags,
            confidence=confidence,
        ),
        request_id,
    )


@mcp.tool(description="Generate a persisted update Candidate for an existing formal page.")
def create_update_candidate(
    page: str,
    title: str,
    source: str | None = None,
    instruction: str | None = None,
    new_sections: list[str] | None = None,
    new_sources: list[str] | None = None,
    new_wikilinks: list[str] | None = None,
    reason_for_update: str | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Generate an update Candidate for an existing formal wiki page."""

    return _public_call(
        lambda: candidates.create_persisted_update_candidate(
            paths,
            page=page,
            title=title,
            source=source,
            instruction=instruction,
            new_sections=new_sections,
            new_sources=new_sources,
            new_wikilinks=new_wikilinks,
            reason_for_update=reason_for_update,
        ),
        request_id,
    )


@mcp.tool(description="Apply an approved Candidate bundle atomically.")
def apply_candidate(
    candidate_id: str,
    approved: bool,
    bundle_id: str | None = None,
    expected_status: str | None = None,
    base_hashes: dict[str, str] | None = None,
    ops: list[dict[str, Any]] | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Apply a reviewed Candidate bundle to the wiki."""

    def run() -> dict[str, Any]:
        if not config.allow_write_formal:
            raise PermissionError("Formal page writes are disabled by config")
        return candidates.apply_candidate(
            paths,
            candidate_id,
            approved=approved,
            bundle_id=bundle_id,
            expected_status=expected_status,
            base_hashes=base_hashes,
            ops=ops,
        )

    return _public_call(run, request_id)


@mcp.tool(description="Run wiki lint and return structured lint results.")
def run_lint(
    mode: str = "full",
    timeout_seconds: float = 60.0,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Run the wiki lint script with a timeout and structured error output."""

    return _public_call(
        lambda: lint.run_lint(paths, mode=mode, timeout_seconds=timeout_seconds),
        request_id,
    )


@mcp.tool(description="Summarize wiki health across lint, sources, duplicates, stale pages, and confidence.")
def knowledge_health_review(request_id: str | None = None) -> dict[str, Any]:
    """Return a long-term governance health report."""

    return _public_call(lambda: advanced.knowledge_health_review(paths), request_id)


@mcp.tool(description="Render a public-site markdown draft candidate without publishing it.")
def write_public_draft(
    page: str,
    title: str | None = None,
    redact: bool = True,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Clean frontmatter/wikilinks and return a public draft candidate."""

    return _public_call(
        lambda: advanced.write_public_draft(
            paths, page=page, title=title, redact=redact
        ),
        request_id,
    )


@mcp.tool(description="Validate public-site candidate content for sensitive material.")
def validate_public_safety(
    content: str | None = None,
    page: str | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Check public content or a formal page for safety issues."""

    return _public_call(
        lambda: advanced.validate_public_safety(paths, content=content, page=page),
        request_id,
    )


def main() -> None:
    """Start the llm-wiki MCP server over stdio transport."""

    mcp.run("stdio")

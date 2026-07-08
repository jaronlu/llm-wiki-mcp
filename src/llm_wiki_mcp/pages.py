"""Formal wiki page readers and wikilink extraction."""

from __future__ import annotations

import re
from typing import Any

from .content import DEFAULT_CONTENT_LIMIT, slice_content
from .frontmatter import parse_markdown, title_from_content
from .paths import WikiPaths

WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)")


def extract_wikilinks(text: str) -> list[str]:
    """Extract unique Obsidian-style wikilink targets from markdown text."""

    seen: set[str] = set()
    links: list[str] = []
    for match in WIKILINK_RE.finditer(text):
        link = match.group(1).strip()
        if link and link not in seen:
            seen.add(link)
            links.append(link)
    return links


def _page_slug(paths: WikiPaths, page_path: Any) -> str:
    """Return the extensionless wiki slug for a formal page path."""

    rel = paths.rel(page_path)
    return rel[:-3] if rel.endswith(".md") else rel


def _extract_backlinks(paths: WikiPaths, page_path: Any) -> list[str]:
    """Find formal pages that link to the requested formal page."""

    target_slug = _page_slug(paths, page_path)
    target_names = {target_slug, f"{target_slug}.md"}
    backlinks: list[str] = []
    for dirname in paths.formal_dirs:
        base = paths.root / dirname
        if not base.exists():
            continue
        for candidate in sorted(base.rglob("*.md")):
            if candidate == page_path:
                continue
            if not paths.is_formal_page(candidate):
                continue
            parsed = parse_markdown(candidate.read_text(errors="replace"))
            links = set(extract_wikilinks(parsed.content))
            if links & target_names:
                backlinks.append(paths.rel(candidate))
    return backlinks


def read_page(
    paths: WikiPaths,
    page: str,
    offset: int = 0,
    limit: int = DEFAULT_CONTENT_LIMIT,
) -> dict[str, Any]:
    """Read a formal wiki page or slug with frontmatter and bounded content."""

    file_path = paths.require_formal_page(page)
    text = file_path.read_text(errors="replace")
    parsed = parse_markdown(text)
    sliced = slice_content(parsed.content, offset=offset, limit=limit)
    warnings = [] if parsed.has_frontmatter else ["missing YAML frontmatter"]
    return {
        "path": paths.rel(file_path),
        "frontmatter": parsed.frontmatter,
        "has_frontmatter": parsed.has_frontmatter,
        "warnings": warnings,
        "title": parsed.frontmatter.get("title") or title_from_content(parsed.content),
        **sliced,
        "wikilinks": extract_wikilinks(parsed.content),
        "backlinks": _extract_backlinks(paths, file_path),
    }

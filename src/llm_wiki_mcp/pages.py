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
    return {
        "path": paths.rel(file_path),
        "frontmatter": parsed.frontmatter,
        "has_frontmatter": parsed.has_frontmatter,
        "title": parsed.frontmatter.get("title") or title_from_content(parsed.content),
        **sliced,
        "wikilinks": extract_wikilinks(parsed.content),
    }

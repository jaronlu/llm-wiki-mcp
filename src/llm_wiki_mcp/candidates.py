"""Candidate generators for formal pages and index updates.

These helpers intentionally return proposed content only. They do not write formal
pages or mutate index.md, preserving the Phase 2 candidate-first boundary.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import re
import yaml

from .frontmatter import VALID_CONFIDENCE, VALID_PAGE_TYPES
from .paths import WikiPaths


def _today() -> str:
    """Return today's local ISO date for candidate metadata defaults."""

    return date.today().isoformat()


def _formal_candidate_path(paths: WikiPaths, path: str | Path) -> Path:
    """Resolve a non-existing formal markdown path for candidate generation."""

    normalized = paths.markdown_path(path)
    resolved = paths.resolve(normalized)
    rel = paths.rel(resolved)
    if not paths.is_formal_page(resolved):
        raise ValueError("formal page candidate must be under configured formal_dirs")
    if resolved.suffix != ".md":
        raise ValueError(f"formal page candidate must be markdown: {rel}")
    if resolved.exists():
        raise FileExistsError(f"formal page already exists: {rel}")
    return resolved


def _validate_candidate_metadata(
    page_type: str,
    tags: list[str],
    sources: list[str],
    confidence: str,
) -> None:
    """Validate formal page candidate metadata before rendering markdown."""

    if page_type not in VALID_PAGE_TYPES:
        raise ValueError(f"invalid type: {page_type}")
    if confidence not in VALID_CONFIDENCE:
        raise ValueError(f"invalid confidence: {confidence}")
    if not isinstance(tags, list) or not all(isinstance(tag, str) and tag for tag in tags):
        raise ValueError("tags must be a non-empty list of strings")
    if not isinstance(sources, list) or not all(isinstance(source, str) and source for source in sources):
        raise ValueError("sources must be a non-empty list of strings")



def _render_candidate_markdown(
    title: str,
    created: str,
    updated: str,
    page_type: str,
    tags: list[str],
    sources: list[str],
    confidence: str,
    body: str,
    summary: str | None = None,
) -> str:
    """Render a formal wiki page candidate with YAML-safe frontmatter."""

    frontmatter: dict[str, Any] = {
        "title": title,
        "created": created,
        "updated": updated,
        "type": page_type,
        "tags": tags,
        "sources": sources,
        "confidence": confidence,
    }
    if summary:
        frontmatter["summary"] = summary
    yaml_text = yaml.safe_dump(frontmatter, allow_unicode=True, sort_keys=False)
    normalized_body = body if body.endswith("\n") else f"{body}\n"
    return f"---\n{yaml_text}---\n\n{normalized_body}"


def create_formal_page_candidate(
    paths: WikiPaths,
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
    """Return a formal page markdown candidate without writing it to disk."""

    if not title.strip():
        raise ValueError("title must not be empty")
    if not body.strip():
        raise ValueError("body must not be empty")
    _validate_candidate_metadata(page_type, tags, sources, confidence)
    file_path = _formal_candidate_path(paths, path)
    created_value = created or _today()
    updated_value = updated or created_value
    content = _render_candidate_markdown(
        title=title,
        created=created_value,
        updated=updated_value,
        page_type=page_type,
        tags=tags,
        sources=sources,
        confidence=confidence,
        summary=summary,
        body=body,
    )
    return {
        "candidate": True,
        "would_write": False,
        "exists": False,
        "path": paths.rel(file_path),
        "frontmatter": {
            "title": title,
            "created": created_value,
            "updated": updated_value,
            "type": page_type,
            "tags": tags,
            "sources": sources,
            "confidence": confidence,
            **({"summary": summary} if summary else {}),
        },
        "content": content,
    }


def _page_slug(paths: WikiPaths, page: str) -> str:
    """Return an extensionless formal page slug suitable for index wikilinks."""

    resolved = paths.resolve(paths.markdown_path(page))
    rel = paths.rel(resolved)
    if not paths.is_formal_page(resolved):
        raise ValueError("index candidate page must be under configured formal_dirs")
    if not rel.endswith(".md"):
        raise ValueError(f"index candidate page must be markdown: {rel}")
    return rel[:-3]


def _indexed_slugs(index_text: str) -> set[str]:
    """Extract normalized formal page slugs from index wikilinks."""

    slugs: set[str] = set()
    for match in re.finditer(r"\[\[([^\]|#]+)", index_text):
        slug = match.group(1).strip()
        if slug.endswith(".md"):
            slug = slug[:-3]
        slugs.add(slug)
    return slugs


def _heading_match(line: str) -> tuple[int, str] | None:
    """Return heading level and text for a Markdown ATX heading line."""

    match = re.match(r"^(#{1,6})\s+(.+?)\s*#*\s*$", line)
    if not match:
        return None
    return len(match.group(1)), match.group(2).strip()


def _insert_under_heading(index_text: str, heading: str, entry: str) -> tuple[str, bool]:
    """Insert an index entry under a markdown heading, creating it if needed."""

    lines = index_text.splitlines()
    normalized_heading = heading.strip().casefold()
    heading_idx: int | None = None
    heading_level: int | None = None
    for idx, line in enumerate(lines):
        parsed = _heading_match(line)
        if parsed and parsed[1].casefold() == normalized_heading:
            heading_idx = idx
            heading_level = parsed[0]
            break

    if heading_idx is None or heading_level is None:
        heading_line = f"## {heading.strip()}"
        suffix = "" if index_text.endswith("\n") else "\n"
        return f"{index_text}{suffix}\n{heading_line}\n\n{entry}\n", True

    insert_idx = heading_idx + 1
    while insert_idx < len(lines):
        parsed = _heading_match(lines[insert_idx])
        if parsed and parsed[0] <= heading_level:
            break
        insert_idx += 1
    while insert_idx > heading_idx + 1 and lines[insert_idx - 1] == "":
        insert_idx -= 1
    lines.insert(insert_idx, entry)
    return "\n".join(lines).rstrip() + "\n", True


def update_index_candidate(
    paths: WikiPaths,
    page: str,
    title: str,
    description: str,
    section_heading: str,
) -> dict[str, Any]:
    """Return an index.md update candidate without mutating index.md."""

    if not title.strip():
        raise ValueError("title must not be empty")
    if not description.strip():
        raise ValueError("description must not be empty")
    if not section_heading.strip():
        raise ValueError("section_heading must not be empty")

    try:
        index_path = paths.require_existing_file("index.md")
    except FileNotFoundError as exc:
        raise FileNotFoundError("index.md not found") from exc

    slug = _page_slug(paths, page)
    index_text = index_path.read_text(errors="replace")
    entry = f"- [[{slug}]] — {description}"
    already_indexed = slug in _indexed_slugs(index_text)
    if already_indexed:
        content = index_text
        inserted = False
    else:
        content, inserted = _insert_under_heading(index_text, section_heading, entry)
    return {
        "candidate": True,
        "would_write": False,
        "path": paths.rel(index_path),
        "page": f"{slug}.md",
        "title": title,
        "section_heading": section_heading,
        "entry": entry,
        "already_indexed": already_indexed,
        "inserted": inserted,
        "content": content,
    }


def create_update_candidate(
    paths: WikiPaths,
    page: str,
    title: str,
    source: str | None = None,
    instruction: str | None = None,
    new_sections: list[str] | None = None,
    new_sources: list[str] | None = None,
    new_wikilinks: list[str] | None = None,
    reason_for_update: str | None = None,
) -> dict[str, Any]:
    """Return an update candidate for an existing formal page without writing it.

    Personal wikis grow more often through incremental updates than fresh pages.
    This candidate tells the caller what would change and why updated is preferred
    over creating a new page.
    """

    if not title.strip():
        raise ValueError("title must not be empty")
    if not page.strip():
        raise ValueError("page must not be empty")

    try:
        file_path = paths.require_formal_page(page)
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"target page not found: {page}") from exc

    rel = paths.rel(file_path)
    updated_date = _today()
    sections = new_sections or []
    sources = new_sources or []
    wikilinks = new_wikilinks or []

    return {
        "candidate": True,
        "would_write": False,
        "page": rel,
        "title": title,
        "source": source,
        "instruction": instruction,
        "reason_for_update": reason_for_update or (
            f"Target page {rel} exists; providing update candidate instead of new page."
        ),
        "suggested_sections": sections,
        "suggested_sources": sources,
        "suggested_wikilinks": wikilinks,
        "updated": updated_date,
    }

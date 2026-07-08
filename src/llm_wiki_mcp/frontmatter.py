"""Markdown frontmatter parsing and validation utilities."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Any

import yaml

from .paths import WikiPaths
from .responses import response_envelope

REQUIRED_FIELDS = (
    "title",
    "created",
    "updated",
    "type",
    "tags",
    "sources",
    "confidence",
)
VALID_PAGE_TYPES = {"concept", "query", "comparison", "summary", "entity", "reference"}
VALID_CONFIDENCE = {"high", "medium", "low"}
TYPE_LINE_RE = re.compile(r"^\s*type\s*:\s*(.+)$", re.MULTILINE)
TYPE_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_-]*")


def _json_safe(value: Any) -> Any:
    """Recursively normalize YAML values into JSON-serializable primitives."""

    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


@dataclass(frozen=True)
class ParsedMarkdown:
    """A markdown document split into parsed YAML frontmatter and body content."""

    frontmatter: dict[str, Any]
    content: str
    has_frontmatter: bool


def parse_markdown(text: str) -> ParsedMarkdown:
    """Parse leading YAML frontmatter from markdown text when present."""

    if not text.startswith("---\n"):
        return ParsedMarkdown(frontmatter={}, content=text, has_frontmatter=False)

    marker = "\n---\n"
    end = text.find(marker, 4)
    if end == -1:
        return ParsedMarkdown(frontmatter={}, content=text, has_frontmatter=False)

    raw_yaml = text[4:end]
    body = text[end + len(marker) :]
    loaded: Any
    try:
        loaded = yaml.safe_load(raw_yaml) or {}
    except yaml.YAMLError as exc:
        return ParsedMarkdown(
            frontmatter={"_parse_error": str(exc)}, content=body, has_frontmatter=False
        )
    if not isinstance(loaded, dict):
        loaded = {}
    return ParsedMarkdown(
        frontmatter=_json_safe(loaded), content=body, has_frontmatter=True
    )


def title_from_content(content: str) -> str | None:
    """Return the first H1 heading from markdown content, if one exists."""

    for line in content.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return None


def page_types_from_schema(paths: WikiPaths) -> set[str]:
    """Return page types declared by SCHEMA.md, falling back to built-in types."""

    schema_path = paths.root / "SCHEMA.md"
    if not schema_path.is_file():
        return set(VALID_PAGE_TYPES)
    text = schema_path.read_text(errors="replace")
    match = TYPE_LINE_RE.search(text)
    if not match:
        return set(VALID_PAGE_TYPES)
    raw_types = match.group(1)
    types = {
        token
        for token in TYPE_TOKEN_RE.findall(raw_types)
        if token not in {"type", "tags", "sources", "confidence"}
    }
    return types or set(VALID_PAGE_TYPES)


def validate_frontmatter(paths: WikiPaths, page: str) -> dict[str, Any]:
    """Validate the required frontmatter shape for an existing formal wiki page."""

    file_path = paths.require_formal_page(page)
    parsed = parse_markdown(file_path.read_text(errors="replace"))
    errors: list[str] = []
    warnings: list[str] = []

    if not parsed.has_frontmatter:
        errors.append("missing YAML frontmatter")
    if "_parse_error" in parsed.frontmatter:
        errors.append(f"invalid YAML frontmatter: {parsed.frontmatter['_parse_error']}")

    frontmatter = parsed.frontmatter
    for field in REQUIRED_FIELDS:
        value = frontmatter.get(field)
        if field not in frontmatter:
            errors.append(f"missing required field: {field}")
        elif value is None or value == "":
            errors.append(f"required field is empty: {field}")

    page_type = frontmatter.get("type")
    valid_page_types = page_types_from_schema(paths)
    if page_type is not None and page_type not in valid_page_types:
        errors.append(f"invalid type: {page_type}")

    tags = frontmatter.get("tags")
    if tags is not None and not isinstance(tags, list):
        errors.append("tags must be a list")

    sources = frontmatter.get("sources")
    if sources is not None and not isinstance(sources, list):
        errors.append("sources must be a list")

    confidence = frontmatter.get("confidence")
    if confidence is not None and confidence not in VALID_CONFIDENCE:
        errors.append(f"invalid confidence: {confidence}")

    title = frontmatter.get("title")
    if title is not None and not isinstance(title, str):
        errors.append("title must be a string")

    for date_field in ("created", "updated"):
        value = frontmatter.get(date_field)
        if value is not None and not isinstance(value, (str, date)):
            warnings.append(f"{date_field} should be a YYYY-MM-DD string")

    return {
        **response_envelope(
            warnings=warnings,
            errors=errors,
            next_action="fix_frontmatter" if errors else "none",
        ),
        "path": paths.rel(file_path),
        "valid": not errors,
        "has_frontmatter": parsed.has_frontmatter,
        "frontmatter": frontmatter,
    }

"""Markdown frontmatter parsing utilities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import yaml


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
    body = text[end + len(marker):]
    loaded = yaml.safe_load(raw_yaml) or {}
    if not isinstance(loaded, dict):
        loaded = {}
    return ParsedMarkdown(frontmatter=loaded, content=body, has_frontmatter=True)


def title_from_content(content: str) -> str | None:
    """Return the first H1 heading from markdown content, if one exists."""

    for line in content.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return None

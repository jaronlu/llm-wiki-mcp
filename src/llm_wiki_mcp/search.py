from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

from .frontmatter import parse_markdown, title_from_content
from .paths import WikiPaths

FORMAL_DIRS = ("domains", "entities")
RAW_DIRS = ("raw",)


def _iter_markdown(root: Path, dirs: Iterable[str]) -> Iterable[Path]:
    for dirname in dirs:
        base = root / dirname
        if not base.exists():
            continue
        yield from base.rglob("*.md")


def _load_indexed_slugs(paths: WikiPaths) -> set[str]:
    index = paths.root / "index.md"
    if not index.exists():
        return set()
    text = index.read_text(errors="replace")
    return {match.group(1).strip() for match in re.finditer(r"\[\[([^\]|#]+)", text)}


def _matches_domain(paths: WikiPaths, file_path: Path, domain: str | None) -> bool:
    if not domain:
        return True
    rel_parts = Path(paths.rel(file_path)).parts
    return len(rel_parts) >= 3 and rel_parts[0] == "domains" and rel_parts[1] == domain


def _snippet(text: str, terms: list[str], max_len: int = 220) -> str:
    lower = text.lower()
    positions = [lower.find(term) for term in terms if term]
    positions = [pos for pos in positions if pos >= 0]
    pos = min(positions) if positions else 0
    start = max(0, pos - max_len // 3)
    end = min(len(text), start + max_len)
    return " ".join(text[start:end].split())


def search_wiki(
    paths: WikiPaths,
    query: str,
    scope: str = "formal",
    domain: str | None = None,
    page_type: str = "any",
    limit: int = 20,
) -> dict[str, Any]:
    if not query.strip():
        raise ValueError("query must not be empty")
    scope = scope.lower()
    if scope not in {"formal", "raw", "all"}:
        raise ValueError("scope must be one of: formal, raw, all")
    if limit <= 0:
        raise ValueError("limit must be positive")

    dirs: list[str] = []
    if scope in {"formal", "all"}:
        dirs.extend(FORMAL_DIRS)
    if scope in {"raw", "all"}:
        dirs.extend(RAW_DIRS)

    terms = [term.lower() for term in query.split() if term.strip()]
    indexed = _load_indexed_slugs(paths)
    results: list[dict[str, Any]] = []

    for file_path in _iter_markdown(paths.root, dirs):
        rel = paths.rel(file_path)
        if rel.startswith("domains/") and not _matches_domain(paths, file_path, domain):
            continue
        text = file_path.read_text(errors="replace")
        parsed = parse_markdown(text)
        is_formal = rel.startswith("domains/") or rel.startswith("entities/")
        if page_type != "any" and parsed.frontmatter.get("type") != page_type:
            continue

        haystack = "\n".join([
            str(parsed.frontmatter.get("title", "")),
            " ".join(map(str, parsed.frontmatter.get("tags", []) or [])),
            parsed.content,
        ]).lower()
        if not all(term in haystack for term in terms):
            continue

        slug = rel[:-3] if rel.endswith(".md") else rel
        results.append({
            "path": rel,
            "title": parsed.frontmatter.get("title") or title_from_content(parsed.content),
            "type": parsed.frontmatter.get("type"),
            "tags": parsed.frontmatter.get("tags", []) or [],
            "sources": parsed.frontmatter.get("sources", []) or [],
            "confidence": parsed.frontmatter.get("confidence"),
            "indexed": slug in indexed if is_formal else False,
            "snippet": _snippet(text, terms),
        })
        if len(results) >= limit:
            break

    return {"query": query, "scope": scope, "count": len(results), "results": results}

"""Text search over formal wiki pages and raw sources."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

from .frontmatter import parse_markdown, title_from_content
from .paths import WikiPaths
from .responses import response_envelope


def _iter_markdown(root: Path, dirs: Iterable[str]) -> Iterable[Path]:
    """Yield markdown files under selected top-level directories if present."""

    for dirname in dirs:
        base = root / dirname
        if not base.exists():
            continue
        yield from base.rglob("*.md")


def _load_indexed_slugs(paths: WikiPaths) -> set[str]:
    """Return formal page slugs registered in index.md wikilinks."""

    index = paths.root / "index.md"
    if not index.exists():
        return set()
    text = index.read_text(errors="replace")
    return {match.group(1).strip() for match in re.finditer(r"\[\[([^\]|#]+)", text)}


def _matches_domain(paths: WikiPaths, file_path: Path, domain: str | None) -> bool:
    """Return whether a formal page belongs to the requested domain filter."""

    if not domain:
        return True
    rel_parts = Path(paths.rel(file_path)).parts
    return len(rel_parts) >= 3 and rel_parts[0] == "domains" and rel_parts[1] == domain


def _snippet(text: str, terms: list[str], max_len: int = 220) -> str:
    """Build a compact snippet around the first matched query term."""

    lower = text.lower()
    positions = [lower.find(term) for term in terms if term]
    positions = [pos for pos in positions if pos >= 0]
    pos = min(positions) if positions else 0
    start = max(0, pos - max_len // 3)
    end = min(len(text), start + max_len)
    return " ".join(text[start:end].split())


def _query_terms(query: str) -> list[str]:
    """Tokenize a natural-language query into stable case-folded search terms."""

    # Keep hyphenated identifiers such as ``llm-wiki-mcp`` intact while still
    # splitting prose punctuation. Chinese phrases separated by spaces remain
    # individual terms, matching how users naturally type mixed CN/EN queries.
    return [term.casefold() for term in re.findall(r"[\w\-]+", query) if term.strip()]


def _field_text(value: Any) -> str:
    """Return a lowercase searchable string for frontmatter values."""

    if isinstance(value, list):
        return " ".join(map(str, value)).casefold()
    return str(value or "").casefold()


def _match_score(
    *, phrase: str, terms: list[str], path: str, title: str, tags: str, body: str
) -> int:
    """Score partial query matches, weighting high-signal metadata above body text."""

    searchable = "\n".join([path, title, tags, body])
    score = 0
    matched_terms = 0
    for term in terms:
        term_score = 0
        if term in title:
            term_score += 5
        if term in path:
            term_score += 4
        if term in tags:
            term_score += 3
        if term in body:
            term_score += 1
        if term_score:
            matched_terms += 1
            score += term_score
    if phrase and phrase in searchable:
        score += 10
    # Prefer pages that cover more of a long query over pages that only match
    # one generic term such as "MCP".
    score += matched_terms * 2
    return score


def search_wiki(
    paths: WikiPaths,
    query: str,
    scope: str = "formal",
    domain: str | None = None,
    page_type: str = "any",
    limit: int = 20,
) -> dict[str, Any]:
    """Search selected wiki zones and return metadata-rich result objects."""

    if not query.strip():
        raise ValueError("query must not be empty")
    scope = scope.lower()
    if scope not in {"formal", "raw", "all"}:
        raise ValueError("scope must be one of: formal, raw, all")
    if limit <= 0:
        raise ValueError("limit must be positive")

    dirs: list[str] = []
    if scope in {"formal", "all"}:
        dirs.extend(paths.formal_dirs)
    if scope in {"raw", "all"}:
        dirs.extend(paths.raw_dirs)

    terms = _query_terms(query)
    phrase = query.casefold().strip()
    indexed = _load_indexed_slugs(paths)
    scored_results: list[tuple[int, dict[str, Any]]] = []

    for file_path in _iter_markdown(paths.root, dirs):
        rel = paths.rel(file_path)
        if rel.startswith("domains/") and not _matches_domain(paths, file_path, domain):
            continue
        text = file_path.read_text(errors="replace")
        parsed = parse_markdown(text)
        is_formal = paths.is_formal_page(file_path)
        if page_type != "any" and parsed.frontmatter.get("type") != page_type:
            continue

        title = _field_text(
            parsed.frontmatter.get("title") or title_from_content(parsed.content)
        )
        tags = _field_text(parsed.frontmatter.get("tags", []) or [])
        body = parsed.content.casefold()
        score = _match_score(
            phrase=phrase,
            terms=terms,
            path=rel.casefold(),
            title=title,
            tags=tags,
            body=body,
        )
        if score <= 0:
            continue

        slug = rel[:-3] if rel.endswith(".md") else rel
        scored_results.append(
            (
                score,
                {
                    "path": rel,
                    "title": parsed.frontmatter.get("title")
                    or title_from_content(parsed.content),
                    "type": parsed.frontmatter.get("type"),
                    "tags": parsed.frontmatter.get("tags", []) or [],
                    "sources": parsed.frontmatter.get("sources", []) or [],
                    "confidence": parsed.frontmatter.get("confidence"),
                    "indexed": slug in indexed if is_formal else False,
                    "snippet": _snippet(text, terms),
                    "score": score,
                },
            )
        )

    scored_results.sort(key=lambda item: (-item[0], item[1]["path"]))
    results = [result for _, result in scored_results[:limit]]
    return {
        **response_envelope(next_action="read_page" if results else "refine_query"),
        "query": query,
        "scope": scope,
        "count": len(results),
        "results": results,
    }

"""Related-page discovery for formal llm-wiki pages."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .frontmatter import parse_markdown, title_from_content
from .paths import WikiPathError, WikiPaths
from .responses import response_envelope

TOKEN_RE = re.compile(r"[\w\u4e00-\u9fff]+")
MAX_RELATED_LIMIT = 50


def _tokens(text: str) -> set[str]:
    """Tokenize Latin/CJK text into lowercase terms for lightweight scoring."""

    return {
        token.lower() for token in TOKEN_RE.findall(text) if len(token.strip()) >= 2
    }


def _iter_formal_pages(paths: WikiPaths) -> list[Path]:
    """Return formal markdown pages under configured formal directories."""

    files: list[Path] = []
    for dirname in paths.formal_dirs:
        base = paths.root / dirname
        if not base.exists():
            continue
        for candidate in sorted(base.rglob("*.md")):
            try:
                paths.rel(candidate)
            except WikiPathError:
                continue
            files.append(candidate)
    return files


def _page_document(paths: WikiPaths, file_path: Path) -> dict[str, Any]:
    """Load a formal page into fields used by the related-page scorer."""

    text = file_path.read_text(errors="replace")
    parsed = parse_markdown(text)
    title = (
        parsed.frontmatter.get("title")
        or title_from_content(parsed.content)
        or paths.rel(file_path)
    )
    tags = parsed.frontmatter.get("tags", []) or []
    if not isinstance(tags, list):
        tags = []
    haystack = "\n".join([
        str(title),
        " ".join(map(str, tags)),
        parsed.content,
    ])
    return {
        "path": paths.rel(file_path),
        "title": title,
        "type": parsed.frontmatter.get("type"),
        "tags": tags,
        "tokens": _tokens(haystack),
        "snippet": " ".join(parsed.content.split())[:220],
    }


def _matches_domain(paths: WikiPaths, file_path: Path, domain: str | None) -> bool:
    """Return whether a page belongs to the requested domains/<domain>/ zone."""

    if not domain:
        return True
    rel_parts = Path(paths.rel(file_path)).parts
    return len(rel_parts) >= 3 and rel_parts[0] == "domains" and rel_parts[1] == domain


def _score(
    candidate: dict[str, Any], query_tokens: set[str], query_tags: set[str]
) -> tuple[int, list[str]]:
    """Score a candidate by token and tag overlap."""

    matched_terms = sorted(candidate["tokens"] & query_tokens)
    candidate_tags = {str(tag).lower() for tag in candidate.get("tags", [])}
    matched_tags = sorted(candidate_tags & query_tags)
    score = len(matched_terms) + (3 * len(matched_tags))
    return score, [*matched_tags, *matched_terms[:8]]


def find_related_pages(
    paths: WikiPaths,
    topic: str,
    domain: str | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    """Find formal pages related to a topic before creating or updating pages."""

    if not topic.strip():
        raise ValueError("topic must not be empty")
    if limit <= 0:
        raise ValueError("limit must be positive")
    if limit > MAX_RELATED_LIMIT:
        raise ValueError(f"limit must be <= {MAX_RELATED_LIMIT}")

    query_tokens = _tokens(topic)
    query_tags: set[str] = {domain.lower()} if domain else set()

    results: list[dict[str, Any]] = []
    for file_path in _iter_formal_pages(paths):
        if not _matches_domain(paths, file_path, domain):
            continue
        candidate = _page_document(paths, file_path)
        score, matched_terms = _score(candidate, query_tokens, query_tags)
        if score <= 0:
            continue
        results.append({
            "path": candidate["path"],
            "title": candidate["title"],
            "type": candidate["type"],
            "tags": candidate["tags"],
            "score": score,
            "reason": f"matched: {', '.join(matched_terms)}"
            if matched_terms
            else "matched topic",
            "matched_terms": matched_terms,
            "snippet": candidate["snippet"],
        })

    results.sort(key=lambda item: (-item["score"], item["path"]))
    kept = results[:limit]
    return {
        **response_envelope(
            next_action="create_update_candidate"
            if kept
            else "create_formal_page_candidate"
        ),
        "topic": topic,
        "domain": domain,
        "count": len(kept),
        "results": kept,
    }

"""Phase 3 workflow, public-draft, manifest, and health-review helpers."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import tempfile
from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Iterable

from .candidates import create_formal_page_candidate
from .frontmatter import parse_markdown, title_from_content
from .paths import WikiPathError, WikiPaths
from .related import find_related_pages
from .responses import candidate_envelope, response_envelope

TOKEN_RE = re.compile(r"[\w\u4e00-\u9fff\-]+")
WIKILINK_WITH_ALIAS_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|([^\]]+))?\]\]")
MANIFEST_PATH = ".llm-wiki/source-manifest.json"
MAX_HEALTH_ITEMS = 20
PAGE_TYPE_DIRS = {
    "concept": "concepts",
    "query": "queries",
    "comparison": "comparisons",
    "summary": "summaries",
    "reference": "references",
    "entity": "",
}

PUBLIC_SAFETY_PATTERNS: tuple[tuple[str, str], ...] = (
    ("private_path", r"/Users/[A-Za-z0-9._-]+|[A-Z]:\\Users\\[A-Za-z0-9._-]+"),
    ("secret", r"(?i)(api[_-]?key|token|password|secret)\s*[:=]\s*['\"]?[^'\"\s]+"),
    ("private_key", r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    ("salary", r"(?i)(salary|薪资|薪水|base|offer|compensation|年包|月薪)"),
    ("interview", r"(?i)(interview|面试|面经|求职|跳槽|简历)"),
    ("internal_project", r"(?i)(internal|confidential|公司内部|内部项目|私有项目)"),
    ("raw_reference", r"raw/[^\s)\]]+"),
)


@dataclass(frozen=True)
class PageDoc:
    """Loaded markdown page with parsed metadata."""

    path: Path
    rel: str
    title: str
    content: str
    frontmatter: dict[str, Any]
    is_formal: bool


def _tokens(text: str) -> list[str]:
    """Tokenize mixed Chinese/English text into lowercase terms."""

    return [
        token.casefold() for token in TOKEN_RE.findall(text) if len(token.strip()) >= 2
    ]


def _token_counts(text: str) -> Counter[str]:
    """Return token frequencies for deterministic local similarity."""

    return Counter(_tokens(text))


def _cosine(left: Counter[str], right: Counter[str]) -> float:
    """Compute cosine similarity over sparse token-count vectors."""

    if not left or not right:
        return 0.0
    shared = set(left) & set(right)
    dot = sum(left[token] * right[token] for token in shared)
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))
    if not left_norm or not right_norm:
        return 0.0
    return dot / (left_norm * right_norm)


def _iter_markdown(paths: WikiPaths, dirs: Iterable[str]) -> Iterable[Path]:
    """Yield markdown files under configured top-level directories."""

    for dirname in dirs:
        base = paths.root / dirname
        if not base.exists():
            continue
        for candidate in sorted(base.rglob("*.md")):
            try:
                paths.rel(candidate)
            except WikiPathError:
                continue
            yield candidate


def _iter_formal_docs(paths: WikiPaths) -> list[PageDoc]:
    """Load all configured formal markdown pages."""

    docs: list[PageDoc] = []
    for file_path in _iter_markdown(paths, paths.formal_dirs):
        text = file_path.read_text(errors="replace")
        parsed = parse_markdown(text)
        rel = paths.rel(file_path)
        docs.append(
            PageDoc(
                path=file_path,
                rel=rel,
                title=parsed.frontmatter.get("title")
                or title_from_content(parsed.content)
                or rel,
                content=parsed.content,
                frontmatter=parsed.frontmatter,
                is_formal=True,
            )
        )
    return docs


def _load_page_doc(paths: WikiPaths, page: str) -> PageDoc:
    """Load a single formal page document."""

    file_path = paths.require_formal_page(page)
    text = file_path.read_text(errors="replace")
    parsed = parse_markdown(text)
    rel = paths.rel(file_path)
    return PageDoc(
        path=file_path,
        rel=rel,
        title=parsed.frontmatter.get("title")
        or title_from_content(parsed.content)
        or rel,
        content=parsed.content,
        frontmatter=parsed.frontmatter,
        is_formal=True,
    )


def _chunk_text(text: str, chunk_chars: int) -> list[tuple[int, str]]:
    """Split text into stable paragraph-aware chunks."""

    paragraphs = [
        paragraph.strip()
        for paragraph in re.split(r"\n\s*\n", text)
        if paragraph.strip()
    ]
    chunks: list[tuple[int, str]] = []
    current: list[str] = []
    current_len = 0
    start = 0
    for paragraph in paragraphs:
        if current and current_len + len(paragraph) + 2 > chunk_chars:
            chunks.append((start, "\n\n".join(current)))
            start += len("\n\n".join(current)) + 2
            current = []
            current_len = 0
        current.append(paragraph)
        current_len += len(paragraph) + 2
    if current:
        chunks.append((start, "\n\n".join(current)))
    return chunks or [(0, text[:chunk_chars])]


def semantic_search(
    paths: WikiPaths,
    query: str,
    scope: str = "formal",
    limit: int = 10,
    chunk_chars: int = 1200,
) -> dict[str, Any]:
    """Return chunk-level similarity results with wiki metadata.

    This uses deterministic local token vectors as the built-in embedding
    baseline, avoiding an external vector database while preserving the same
    formal/raw/draft boundaries required by the design.
    """

    if not query.strip():
        raise ValueError("query must not be empty")
    if scope not in {"formal", "raw", "all"}:
        raise ValueError("scope must be one of: formal, raw, all")
    if limit <= 0:
        raise ValueError("limit must be positive")
    if chunk_chars < 200:
        raise ValueError("chunk_chars must be >= 200")

    dirs: list[str] = []
    if scope in {"formal", "all"}:
        dirs.extend(paths.formal_dirs)
    if scope in {"raw", "all"}:
        dirs.extend(paths.raw_dirs)

    query_vector = _token_counts(query)
    results: list[dict[str, Any]] = []
    for file_path in _iter_markdown(paths, dirs):
        rel = paths.rel(file_path)
        text = file_path.read_text(errors="replace")
        parsed = parse_markdown(text)
        body = parsed.content if paths.is_formal_page(file_path) else text
        for chunk_index, (offset, chunk) in enumerate(_chunk_text(body, chunk_chars)):
            score = _cosine(query_vector, _token_counts(chunk))
            if score <= 0:
                continue
            results.append({
                "path": rel,
                "chunk_index": chunk_index,
                "offset": offset,
                "score": round(score, 6),
                "title": parsed.frontmatter.get("title")
                or title_from_content(parsed.content),
                "type": parsed.frontmatter.get("type"),
                "tags": parsed.frontmatter.get("tags", []) or [],
                "sources": parsed.frontmatter.get("sources", []) or [],
                "content": chunk,
            })

    results.sort(key=lambda item: (-item["score"], item["path"], item["chunk_index"]))
    return {
        **response_envelope(next_action="read_page" if results else "refine_query"),
        "query": query,
        "scope": scope,
        "embedding": "local-token-vector",
        "count": min(len(results), limit),
        "results": results[:limit],
    }


def _slugify(text: str) -> str:
    """Create a conservative markdown filename slug."""

    slug = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "-", text.strip().lower()).strip("-")
    return slug or "untitled"


def _first_heading_or_stem(text: str, fallback: str) -> str:
    """Use first H1 heading as title, falling back to filename stem."""

    return title_from_content(text) or fallback.replace("-", " ").strip().title()


def classify_source_candidate(
    paths: WikiPaths,
    source: str,
    intent: str | None = None,
    domain: str | None = None,
) -> dict[str, Any]:
    """Classify where a source should go next in the wiki lifecycle."""

    source_path = paths.require_raw_path(source)
    if not source_path.is_file():
        raise FileNotFoundError(f"File not found: {paths.rel(source_path)}")
    text = source_path.read_text(errors="replace")
    title = _first_heading_or_stem(text, source_path.stem)
    related = find_related_pages(
        paths, topic=f"{title} {intent or ''}", domain=domain, limit=5
    )
    lower = f"{title}\n{text}\n{intent or ''}".casefold()
    if not text.strip() or "ignore" in lower or "忽略" in lower:
        classification = "ignore"
        reason = "source is empty or intent explicitly asks to ignore"
    elif related["results"]:
        classification = "update_existing"
        reason = "related formal pages already exist; prefer strengthening them"
    elif any(term in lower for term in ("draft", "发布稿", "article", "post")):
        classification = "drafts"
        reason = "source looks like a publishable draft or one-off article"
    elif len(text.strip()) < 120:
        classification = "raw"
        reason = "source is short or unstable; keep it as raw evidence"
    else:
        classification = "formal_candidate"
        reason = (
            "no strong related page found; consider an independently recallable page"
        )
    return {
        **response_envelope(),
        "source": paths.rel(source_path),
        "classification": classification,
        "reason": reason,
        "title": title,
        "domain": domain,
        "related_pages": related["results"],
        "next_action": {
            "raw": "keep_raw_only",
            "drafts": "write_public_or_private_draft_candidate",
            "update_existing": "create_update_candidate",
            "formal_candidate": "compile_raw_to_formal_draft",
            "ignore": "no_action",
        }[classification],
    }


def compile_raw_to_formal_draft(
    paths: WikiPaths,
    source: str,
    topic: str | None = None,
    domain: str = "general",
    page_type: str = "concept",
    tags: list[str] | None = None,
    confidence: str = "medium",
) -> dict[str, Any]:
    """Compile a raw source into a formal-page draft candidate."""

    source_path = paths.require_raw_path(source)
    if not source_path.is_file():
        raise FileNotFoundError(f"File not found: {paths.rel(source_path)}")
    rel_source = paths.rel(source_path)
    raw_text = source_path.read_text(errors="replace")
    title = topic or _first_heading_or_stem(raw_text, source_path.stem)
    related = find_related_pages(paths, topic=title, domain=domain, limit=5)
    decision = "update_existing" if related["results"] else "new_page"
    reason = (
        "related formal pages found; review whether this should update an existing page"
        if related["results"]
        else "no related formal page found; a new independently recallable page may be appropriate"
    )
    body = "\n".join([
        "## 核心结论",
        "",
        f"- This is a review draft compiled from `{rel_source}`.",
        "- Treat source facts, agent synthesis, and personal conclusions separately during final editing.",
        "",
        "## Source Facts",
        "",
        raw_text.strip()[:4000],
        "",
        "## Review Notes",
        "",
        f"- Decision: {decision}",
        f"- Reason: {reason}",
        "- Verify wikilinks and evidence boundaries before applying.",
    ])
    slug = _slugify(title)
    type_dir = PAGE_TYPE_DIRS.get(page_type, f"{page_type}s")
    candidate_path = (
        f"entities/{slug}.md"
        if page_type == "entity"
        else f"domains/{domain}/{type_dir}/{slug}.md"
    )
    candidate = create_formal_page_candidate(
        paths,
        path=candidate_path,
        title=title,
        page_type=page_type,
        tags=tags or [domain],
        sources=[rel_source],
        confidence=confidence,
        body=body,
    )
    return {
        **candidate,
        "source": rel_source,
        "decision": decision,
        "reason": reason,
        "related_pages": related["results"],
        "evidence_layers": [
            "source_fact",
            "agent_synthesis",
            "personal_conclusion",
            "hypothesis",
            "verified_external",
        ],
    }


def _strip_frontmatter(text: str) -> str:
    """Remove leading YAML frontmatter from markdown text."""

    parsed = parse_markdown(text)
    return parsed.content if parsed.has_frontmatter else text


def _wikilinks_to_text(text: str) -> str:
    """Convert Obsidian wikilinks to plain public markdown text."""

    def replace(match: re.Match[str]) -> str:
        target = match.group(1).strip()
        alias = match.group(2)
        return alias.strip() if alias else Path(target).name.replace("-", " ")

    return WIKILINK_WITH_ALIAS_RE.sub(replace, text)


def validate_public_safety(
    paths: WikiPaths, content: str | None = None, page: str | None = None
) -> dict[str, Any]:
    """Check whether public-site candidate content contains sensitive material."""

    if bool(content) == bool(page):
        raise ValueError("provide exactly one of content or page")
    if page:
        file_path = paths.require_formal_page(page)
        text = file_path.read_text(errors="replace")
        rel = paths.rel(file_path)
    else:
        text = content or ""
        rel = None

    issues: list[dict[str, Any]] = []
    for kind, pattern in PUBLIC_SAFETY_PATTERNS:
        for match in re.finditer(pattern, text):
            start = max(0, match.start() - 40)
            end = min(len(text), match.end() + 40)
            issues.append({
                "kind": kind,
                "match": match.group(0)[:80],
                "snippet": " ".join(text[start:end].split()),
            })
    return {
        **response_envelope(
            warnings=[] if not issues else ["public safety issues found"],
            errors=[],
            next_action="review_issues" if issues else "none",
        ),
        "safe": not issues,
        "page": rel,
        "issues": issues,
        "issue_count": len(issues),
    }


def _redact_public_text(text: str) -> str:
    """Redact common sensitive patterns in public-draft output."""

    redacted = text
    for _, pattern in PUBLIC_SAFETY_PATTERNS:
        redacted = re.sub(pattern, "[REDACTED]", redacted)
    return redacted


def write_public_draft(
    paths: WikiPaths, page: str, title: str | None = None, redact: bool = True
) -> dict[str, Any]:
    """Return a public-site markdown draft candidate without writing or publishing."""

    file_path = paths.require_formal_page(page)
    text = file_path.read_text(errors="replace")
    parsed = parse_markdown(text)
    body = _wikilinks_to_text(_strip_frontmatter(text)).strip()
    if redact:
        body = _redact_public_text(body)
    public_title = (
        title
        or parsed.frontmatter.get("title")
        or title_from_content(parsed.content)
        or file_path.stem
    )
    content = f"# {public_title}\n\n{body}\n"
    safety = validate_public_safety(paths, content=content)
    return {
        **candidate_envelope(
            warnings=[] if safety["safe"] else ["public safety issues found"]
        ),
        "would_publish": False,
        "source_page": paths.rel(file_path),
        "title": public_title,
        "content": content,
        "safety": safety,
    }


def _manifest_path(paths: WikiPaths) -> Path:
    """Return the configured sidecar source manifest path."""

    return paths.resolve(MANIFEST_PATH)


def _sha256(path: Path) -> str:
    """Hash a file's bytes."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_manifest(paths: WikiPaths) -> dict[str, dict[str, Any]]:
    """Read sidecar source manifest if present."""

    path = _manifest_path(paths)
    if not path.exists():
        return {}
    loaded = json.loads(path.read_text())
    if not isinstance(loaded, dict):
        raise ValueError("source manifest must contain a JSON object")
    return {str(key): value for key, value in loaded.items() if isinstance(value, dict)}


def _atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    """Atomically write formatted JSON."""

    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def find_referencing_pages(paths: WikiPaths, source: str) -> dict[str, Any]:
    """Find formal pages whose frontmatter.sources reference a raw source."""

    source_path = paths.require_raw_path(source)
    rel_source = paths.rel(source_path)
    pages: list[dict[str, Any]] = []
    for doc in _iter_formal_docs(paths):
        sources = doc.frontmatter.get("sources", []) or []
        if isinstance(sources, list) and rel_source in [str(item) for item in sources]:
            pages.append({
                "path": doc.rel,
                "title": doc.title,
                "type": doc.frontmatter.get("type"),
                "tags": doc.frontmatter.get("tags", []) or [],
            })
    return {
        **response_envelope(
            next_action="create_update_candidate"
            if pages
            else "create_formal_page_candidate"
        ),
        "source": rel_source,
        "count": len(pages),
        "pages": pages,
    }


def detect_new_source(paths: WikiPaths, source: str | None = None) -> dict[str, Any]:
    """Detect raw sources absent from or changed since the source manifest."""

    manifest = _load_manifest(paths)
    raw_files = (
        [paths.require_raw_path(source)]
        if source
        else list(_iter_markdown(paths, paths.raw_dirs))
    )
    changes: list[dict[str, Any]] = []
    for file_path in raw_files:
        if not file_path.is_file():
            continue
        rel = paths.rel(file_path)
        digest = _sha256(file_path)
        previous = manifest.get(rel)
        status = (
            "new"
            if previous is None
            else "changed"
            if previous.get("sha256") != digest
            else "unchanged"
        )
        if status == "unchanged":
            continue
        references = find_referencing_pages(paths, rel)
        suggested_action = (
            "create_formal_page_candidate"
            if references["count"] == 0
            else "create_update_candidate"
        )
        changes.append({
            "path": rel,
            "status": status,
            "sha256": digest,
            "referencing_pages": references["pages"],
            "suggested_action": suggested_action,
        })
    return {
        **response_envelope(next_action="review_source_changes" if changes else "none"),
        "manifest": MANIFEST_PATH,
        "count": len(changes),
        "changes": changes,
    }


def update_source_manifest(
    paths: WikiPaths, sources: list[str] | None = None
) -> dict[str, Any]:
    """Update the sidecar raw source digest manifest."""

    manifest = _load_manifest(paths)
    raw_files = (
        [paths.require_raw_path(source) for source in sources]
        if sources
        else list(_iter_markdown(paths, paths.raw_dirs))
    )
    updated: list[str] = []
    for file_path in raw_files:
        if not file_path.is_file():
            continue
        rel = paths.rel(file_path)
        manifest[rel] = {
            "sha256": _sha256(file_path),
            "updated": date.today().isoformat(),
        }
        updated.append(rel)
    path = _manifest_path(paths)
    _atomic_write_json(path, manifest)
    return {
        **response_envelope(would_write=True),
        "updated": True,
        "path": paths.rel(path),
        "sources": updated,
        "count": len(updated),
    }


def suggest_wikilinks(
    paths: WikiPaths, text: str, limit: int = 10, domain: str | None = None
) -> dict[str, Any]:
    """Suggest formal page wikilinks for candidate content."""

    if limit <= 0:
        raise ValueError("limit must be positive")
    query_vector = _token_counts(text)
    suggestions: list[dict[str, Any]] = []
    for doc in _iter_formal_docs(paths):
        if domain and not doc.rel.startswith(f"domains/{domain}/"):
            continue
        score = _cosine(
            query_vector,
            _token_counts(
                f"{doc.title}\n{' '.join(map(str, doc.frontmatter.get('tags', []) or []))}\n{doc.content}"
            ),
        )
        if score <= 0:
            continue
        slug = doc.rel[:-3] if doc.rel.endswith(".md") else doc.rel
        suggestions.append({
            "path": doc.rel,
            "wikilink": f"[[{slug}]]",
            "title": doc.title,
            "score": round(score, 6),
        })
    suggestions.sort(key=lambda item: (-item["score"], item["path"]))
    return {
        **response_envelope(
            next_action="review_suggestions" if suggestions else "none"
        ),
        "count": min(len(suggestions), limit),
        "suggestions": suggestions[:limit],
    }


def find_uncompiled_sources(paths: WikiPaths) -> dict[str, Any]:
    """Find raw files not referenced by any formal page sources."""

    referenced: set[str] = set()
    for doc in _iter_formal_docs(paths):
        sources = doc.frontmatter.get("sources", []) or []
        if isinstance(sources, list):
            referenced.update(str(source) for source in sources)
    raw_sources = [paths.rel(path) for path in _iter_markdown(paths, paths.raw_dirs)]
    uncompiled = sorted(source for source in raw_sources if source not in referenced)
    return {
        **response_envelope(
            next_action="compile_or_ignore_sources" if uncompiled else "none"
        ),
        "count": len(uncompiled),
        "sources": uncompiled,
    }


def find_duplicate_topics(
    paths: WikiPaths, threshold: float = 0.55, limit: int = 20
) -> dict[str, Any]:
    """Find formal pages with overlapping titles/tags/content."""

    docs = _iter_formal_docs(paths)
    duplicates: list[dict[str, Any]] = []
    vectors = {
        doc.rel: _token_counts(
            f"{doc.title}\n{' '.join(map(str, doc.frontmatter.get('tags', []) or []))}\n{doc.content[:2000]}"
        )
        for doc in docs
    }
    for index, left in enumerate(docs):
        for right in docs[index + 1 :]:
            score = _cosine(vectors[left.rel], vectors[right.rel])
            if score >= threshold:
                duplicates.append({
                    "left": left.rel,
                    "right": right.rel,
                    "score": round(score, 6),
                    "reason": "title/tag/content overlap",
                })
    duplicates.sort(key=lambda item: (-item["score"], item["left"], item["right"]))
    return {
        **response_envelope(
            next_action="suggest_merge_candidates" if duplicates else "none"
        ),
        "threshold": threshold,
        "count": min(len(duplicates), limit),
        "duplicates": duplicates[:limit],
    }


def _parse_iso_date(value: Any) -> date | None:
    """Parse a YYYY-MM-DD value into a date."""

    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def find_stale_pages(
    paths: WikiPaths, older_than_days: int = 365, limit: int = 20
) -> dict[str, Any]:
    """Find pages that have not been updated recently or mention deprecated APIs."""

    cutoff = date.today() - timedelta(days=older_than_days)
    stale: list[dict[str, Any]] = []
    for doc in _iter_formal_docs(paths):
        updated = _parse_iso_date(doc.frontmatter.get("updated"))
        deprecated = bool(
            re.search(r"(?i)\b(deprecated|removed|废弃|移除)\b", doc.content)
        )
        is_old = updated is None or updated < cutoff
        if not is_old and not deprecated:
            continue
        reasons = []
        if is_old:
            reasons.append("updated date is stale or missing")
        if deprecated:
            reasons.append("content mentions deprecated or removed API")
        stale.append({
            "path": doc.rel,
            "title": doc.title,
            "updated": doc.frontmatter.get("updated"),
            "reasons": reasons,
        })
    stale.sort(key=lambda item: (str(item["updated"]), item["path"]))
    return {
        **response_envelope(next_action="refresh_stale_pages" if stale else "none"),
        "older_than_days": older_than_days,
        "count": min(len(stale), limit),
        "pages": stale[:limit],
    }


def find_low_confidence_pages(paths: WikiPaths, limit: int = 20) -> dict[str, Any]:
    """Find formal pages marked confidence: low."""

    pages = [
        {
            "path": doc.rel,
            "title": doc.title,
            "sources": doc.frontmatter.get("sources", []) or [],
            "reason": "confidence is low; needs stronger evidence or verification",
        }
        for doc in _iter_formal_docs(paths)
        if doc.frontmatter.get("confidence") == "low"
    ]
    return {
        **response_envelope(
            next_action="strengthen_low_confidence_pages" if pages else "none"
        ),
        "count": min(len(pages), limit),
        "pages": pages[:limit],
    }


def suggest_merge_candidates(
    paths: WikiPaths, threshold: float = 0.65, limit: int = 10
) -> dict[str, Any]:
    """Suggest merge candidates without deleting or rewriting pages."""

    duplicates = find_duplicate_topics(paths, threshold=threshold, limit=limit)[
        "duplicates"
    ]
    suggestions = [
        {
            "candidate": True,
            "would_write": False,
            "source_page": item["right"],
            "target_page": item["left"],
            "score": item["score"],
            "reason": "high topic overlap; review for merge or redirect",
        }
        for item in duplicates
    ]
    return {
        **response_envelope(
            next_action="review_merge_candidates" if suggestions else "none"
        ),
        "count": len(suggestions),
        "suggestions": suggestions,
    }


def knowledge_health_review(paths: WikiPaths) -> dict[str, Any]:
    """Summarize wiki health across lint, raw compilation, duplicates, stale and low-confidence pages."""

    # Import lazily to avoid a top-level cycle.
    from .lint import run_lint

    lint = run_lint(paths)
    uncompiled = find_uncompiled_sources(paths)
    duplicates = find_duplicate_topics(paths, limit=MAX_HEALTH_ITEMS)
    stale = find_stale_pages(paths, limit=MAX_HEALTH_ITEMS)
    low_confidence = find_low_confidence_pages(paths, limit=MAX_HEALTH_ITEMS)
    score = 100
    score -= min(30, len(lint.get("errors", [])) * 10)
    score -= min(20, uncompiled["count"])
    score -= min(20, duplicates["count"] * 2)
    score -= min(15, stale["count"])
    score -= min(15, low_confidence["count"])
    return {
        **response_envelope(next_action="review_health_next_actions"),
        "score": max(0, score),
        "lint": lint,
        "uncompiled_sources": uncompiled,
        "duplicate_topics": duplicates,
        "stale_pages": stale,
        "low_confidence_pages": low_confidence,
        "next_actions": [
            "fix lint errors first",
            "compile or intentionally ignore uncompiled raw sources",
            "review duplicate topics and merge candidates",
            "refresh stale or deprecated pages",
            "strengthen low-confidence pages with evidence",
        ],
    }


def audit_wiki_structure(paths: WikiPaths) -> dict[str, Any]:
    """Audit structure beyond the minimal inspect_wiki check."""

    missing_dirs = [
        dirname
        for dirname in (*paths.formal_dirs, *paths.raw_dirs, *paths.non_formal_dirs)
        if not (paths.root / dirname).is_dir()
    ]
    formal_without_frontmatter = [
        doc.rel
        for doc in _iter_formal_docs(paths)
        if not parse_markdown(doc.path.read_text(errors="replace")).has_frontmatter
    ]
    return {
        **candidate_envelope(
            next_action="standardize_page_candidate"
            if formal_without_frontmatter
            else "none"
        ),
        "missing_dirs": missing_dirs,
        "formal_pages_without_frontmatter": formal_without_frontmatter,
        "recommendations": [
            "run init_wiki for missing minimal files or directories",
            "use standardize_page_candidate for markdown pages missing frontmatter",
        ],
    }


def standardize_page_candidate(
    paths: WikiPaths, page: str, page_type: str = "concept", confidence: str = "low"
) -> dict[str, Any]:
    """Render a frontmatter-standardized candidate for an existing markdown page."""

    file_path = paths.resolve(paths.markdown_path(page))
    if not file_path.is_file():
        raise FileNotFoundError(f"File not found: {paths.rel(file_path)}")
    text = file_path.read_text(errors="replace")
    parsed = parse_markdown(text)
    title = (
        parsed.frontmatter.get("title")
        or title_from_content(parsed.content)
        or file_path.stem.replace("-", " ").title()
    )
    body = parsed.content if parsed.has_frontmatter else text
    content = "\n".join([
        "---",
        f"title: {title}",
        f"created: {date.today().isoformat()}",
        f"updated: {date.today().isoformat()}",
        f"type: {page_type}",
        "tags: []",
        "sources: []",
        f"confidence: {confidence}",
        "---",
        "",
        body.strip(),
        "",
    ])
    return {
        **candidate_envelope(
            warnings=["sources and tags require human review before applying"]
        ),
        "path": paths.rel(file_path),
        "content": content,
    }

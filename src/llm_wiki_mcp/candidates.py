"""Candidate generators for formal pages and index updates.

These helpers intentionally return proposed content only. They do not write formal
pages or mutate index.md, preserving the Phase 2 candidate-first boundary.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import tempfile
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import yaml

from .frontmatter import VALID_CONFIDENCE, page_types_from_schema
from .log import LogEntry, _split_header_and_entries
from .paths import WikiPaths
from .responses import candidate_envelope

CANDIDATE_STATE_DIR = ".llm-wiki-mcp/candidates"
CANDIDATE_TTL_DAYS = 7
MISSING_HASH = "sha256:missing"


def _today() -> str:
    """Return today's local ISO date for candidate metadata defaults."""

    return date.today().isoformat()


def _now() -> datetime:
    """Return the current UTC time for candidate metadata."""

    return datetime.now(timezone.utc)


def _sha256_bytes(data: bytes) -> str:
    """Return the design-standard prefixed sha256 digest."""

    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def _file_hash(path: Path) -> str:
    """Hash a file, preserving a stable marker for missing targets."""

    if not path.exists():
        return MISSING_HASH
    return _sha256_bytes(path.read_bytes())


def _candidate_cache_dir(paths: WikiPaths) -> Path:
    """Return the default Candidate Cache directory."""

    return paths.resolve(CANDIDATE_STATE_DIR)


def _candidate_path(paths: WikiPaths, candidate_id: str) -> Path:
    """Return the JSON path for a persisted candidate id."""

    if not re.fullmatch(r"cand_[0-9]{8}_[0-9a-f]{12}", candidate_id):
        raise ValueError("invalid candidate_id")
    return _candidate_cache_dir(paths) / f"{candidate_id}.json"


def _atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    """Atomically write a JSON file."""

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


def _bundle_hash(ops: list[dict[str, Any]]) -> str:
    """Hash candidate bundle operations deterministically."""

    payload = json.dumps(ops, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return _sha256_bytes(payload)


def _new_candidate_id(created_at: datetime) -> str:
    """Create a stable candidate id with sortable date prefix."""

    return f"cand_{created_at.strftime('%Y%m%d')}_{uuid.uuid4().hex[:12]}"


def _persist_candidate(
    paths: WikiPaths,
    ops: list[dict[str, Any]],
    *,
    summary: str,
    preview: dict[str, Any],
    base_hash_paths: list[str],
) -> dict[str, Any]:
    """Persist a pending-review Candidate with its atomic operation bundle."""

    created_at = _now()
    candidate_id = _new_candidate_id(created_at)
    bundle_id = f"review_{candidate_id.removeprefix('cand_')}"
    base_hashes = {
        rel_path: _file_hash(paths.resolve(rel_path)) for rel_path in base_hash_paths
    }
    content_hash = _bundle_hash(ops)
    candidate = {
        "candidate_id": candidate_id,
        "bundle_id": bundle_id,
        "created_at": created_at.isoformat(),
        "expires_at": (created_at + timedelta(days=CANDIDATE_TTL_DAYS)).isoformat(),
        "base_hashes": base_hashes,
        "bundle": {
            "content_hash": content_hash,
            "ops": ops,
        },
        "status": "pending_review",
        "review": {
            "approved_by": None,
            "approved_at": None,
            "approval_hash": None,
        },
        "summary": summary,
        "preview": preview,
    }
    _atomic_write_json(_candidate_path(paths, candidate_id), candidate)
    return candidate


def load_candidate(paths: WikiPaths, candidate_id: str) -> dict[str, Any]:
    """Load a persisted candidate from Candidate Cache."""

    path = _candidate_path(paths, candidate_id)
    if not path.is_file():
        raise FileNotFoundError(f"candidate not found: {candidate_id}")
    loaded = json.loads(path.read_text())
    if not isinstance(loaded, dict):
        raise ValueError("candidate cache entry must contain an object")
    return loaded


def _candidate_summary(candidate: dict[str, Any]) -> dict[str, Any]:
    """Return public candidate metadata without duplicating full content."""

    bundle = candidate["bundle"]
    return {
        "candidate_id": candidate["candidate_id"],
        "bundle_id": candidate["bundle_id"],
        "created_at": candidate["created_at"],
        "expires_at": candidate["expires_at"],
        "base_hashes": candidate["base_hashes"],
        "status": candidate["status"],
        "summary": candidate["summary"],
        "preview": candidate["preview"],
        "bundle": {
            "content_hash": bundle["content_hash"],
            "ops": [
                {
                    key: value
                    for key, value in op.items()
                    if key not in {"content", "entry"}
                }
                for op in bundle["ops"]
            ],
        },
    }


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
    paths: WikiPaths,
    page_type: str,
    tags: list[str],
    sources: list[str],
    confidence: str,
) -> None:
    """Validate formal page candidate metadata before rendering markdown."""

    if page_type not in page_types_from_schema(paths):
        raise ValueError(f"invalid type: {page_type}")
    if confidence not in VALID_CONFIDENCE:
        raise ValueError(f"invalid confidence: {confidence}")
    if not isinstance(tags, list) or not all(
        isinstance(tag, str) and tag for tag in tags
    ):
        raise ValueError("tags must be a non-empty list of strings")
    if not isinstance(sources, list) or not all(
        isinstance(source, str) and source for source in sources
    ):
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
    _validate_candidate_metadata(paths, page_type, tags, sources, confidence)
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
        **candidate_envelope(),
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


def _insert_under_heading(
    index_text: str, heading: str, entry: str
) -> tuple[str, bool]:
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
        **candidate_envelope(),
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
        **candidate_envelope(),
        "page": rel,
        "title": title,
        "source": source,
        "instruction": instruction,
        "reason_for_update": reason_for_update
        or (
            f"Target page {rel} exists; providing update candidate instead of new page."
        ),
        "suggested_sections": sections,
        "suggested_sources": sources,
        "suggested_wikilinks": wikilinks,
        "updated": updated_date,
    }


def compile_page(
    paths: WikiPaths,
    source: str,
    topic: str | None = None,
    domain: str = "general",
    page_type: str = "concept",
    tags: list[str] | None = None,
    confidence: str = "medium",
) -> dict[str, Any]:
    """Compile a raw source into a persisted formal-page Candidate bundle."""

    from . import advanced

    draft = advanced.compile_raw_to_formal_draft(
        paths,
        source=source,
        topic=topic,
        domain=domain,
        page_type=page_type,
        tags=tags,
        confidence=confidence,
    )
    page_path = draft["path"]
    index_candidate = update_index_candidate(
        paths,
        page=page_path,
        title=draft["frontmatter"]["title"],
        description=draft.get("summary") or draft["reason"],
        section_heading=domain.title(),
    )
    log_entry = LogEntry(
        action="compile",
        subject=page_path,
        reason=f"Compiled from {draft['source']}",
        changes="created formal page candidate, index update, and source manifest update",
        impact="formal wiki pending review",
        verification="candidate bundle generated; apply_candidate will run stale checks",
    )
    ops = [
        {
            "op": "write_formal_page",
            "path": page_path,
            "content_hash": _sha256_bytes(draft["content"].encode("utf-8")),
            "content": draft["content"],
        },
        {
            "op": "update_index",
            "path": "index.md",
            "content_hash": _sha256_bytes(index_candidate["content"].encode("utf-8")),
            "content": index_candidate["content"],
        },
        {
            "op": "append_log",
            "path": "log.md",
            "content_hash": _sha256_bytes(log_entry.render().encode("utf-8")),
            "entry": log_entry.render(),
        },
        {
            "op": "update_source_manifest",
            "path": ".llm-wiki/source-manifest.json",
            "sources": [draft["source"]],
            "referencing_pages": [page_path],
        },
    ]
    candidate = _persist_candidate(
        paths,
        ops,
        summary=f"Compile {draft['source']} into {page_path}",
        preview={
            "decision": draft["decision"],
            "reason": draft["reason"],
            "source": draft["source"],
            "path": page_path,
            "title": draft["frontmatter"]["title"],
            "related_pages": draft["related_pages"],
            "content_preview": draft["content"][:1200],
        },
        base_hash_paths=[page_path, "index.md", "log.md", ".llm-wiki/source-manifest.json"],
    )
    return _candidate_summary(candidate)


def create_persisted_update_candidate(
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
    """Create a persisted update Candidate for a known formal page."""

    review = create_update_candidate(
        paths,
        page=page,
        title=title,
        source=source,
        instruction=instruction,
        new_sections=new_sections,
        new_sources=new_sources,
        new_wikilinks=new_wikilinks,
        reason_for_update=reason_for_update,
    )
    page_path = paths.require_formal_page(page)
    original = page_path.read_text(errors="replace")
    sections = "\n\n".join(new_sections or []).strip()
    updated_content = original.rstrip()
    if sections:
        updated_content = f"{updated_content}\n\n{sections}\n"
    sources = [source for source in [source, *(new_sources or [])] if source]
    log_entry = LogEntry(
        action="update",
        subject=review["page"],
        reason=review["reason_for_update"],
        changes=instruction or "created update candidate",
        impact="formal wiki pending review",
        verification="candidate bundle generated; apply_candidate will run stale checks",
    )
    ops = [
        {
            "op": "write_formal_page",
            "path": review["page"],
            "content_hash": _sha256_bytes(updated_content.encode("utf-8")),
            "content": updated_content,
        },
        {
            "op": "append_log",
            "path": "log.md",
            "content_hash": _sha256_bytes(log_entry.render().encode("utf-8")),
            "entry": log_entry.render(),
        },
    ]
    if sources:
        ops.append(
            {
                "op": "update_source_manifest",
                "path": ".llm-wiki/source-manifest.json",
                "sources": sources,
                "referencing_pages": [review["page"]],
            }
        )
    candidate = _persist_candidate(
        paths,
        ops,
        summary=f"Update {review['page']}",
        preview={
            **{
                key: value
                for key, value in review.items()
                if key not in {"content", "candidate", "would_write"}
            },
            "content_preview": updated_content[:1200],
        },
        base_hash_paths=[review["page"], "log.md", ".llm-wiki/source-manifest.json"],
    )
    return _candidate_summary(candidate)


def _lock_path(paths: WikiPaths) -> Path:
    """Return the wiki-level apply lock path."""

    return paths.resolve(".llm-wiki-mcp/apply.lock")


def _validate_write_op(paths: WikiPaths, op: dict[str, Any]) -> None:
    """Validate an apply operation path and shape."""

    op_name = op.get("op")
    path = str(op.get("path") or "")
    if op_name == "write_formal_page":
        resolved = paths.resolve(path)
        if not paths.is_formal_page(resolved):
            raise ValueError(f"formal write outside formal_dirs: {path}")
        if resolved.suffix != ".md":
            raise ValueError(f"formal page must be markdown: {path}")
        if not isinstance(op.get("content"), str):
            raise ValueError(f"formal write content missing: {path}")
    elif op_name == "update_index":
        if path != "index.md":
            raise ValueError("update_index may only write index.md")
        if not isinstance(op.get("content"), str):
            raise ValueError("update_index content missing")
    elif op_name == "append_log":
        if path != "log.md":
            raise ValueError("append_log may only target log.md")
        if not isinstance(op.get("entry"), str):
            raise ValueError("append_log entry missing")
    elif op_name == "update_source_manifest":
        if path != ".llm-wiki/source-manifest.json":
            raise ValueError("update_source_manifest path mismatch")
        if not isinstance(op.get("sources"), list):
            raise ValueError("update_source_manifest sources missing")
    else:
        raise ValueError(f"unsupported candidate op: {op_name}")


def _read_json_object(path: Path) -> dict[str, Any]:
    """Read a JSON object, returning an empty object for a missing file."""

    if not path.exists():
        return {}
    loaded = json.loads(path.read_text())
    if not isinstance(loaded, dict):
        raise ValueError(f"JSON file must contain an object: {path}")
    return loaded


def _render_source_manifest(
    paths: WikiPaths,
    op: dict[str, Any],
    candidate_id: str,
    applied_at: str,
) -> str:
    """Render updated Source Manifest JSON for an apply operation."""

    manifest_path = paths.resolve(op["path"])
    manifest = _read_json_object(manifest_path)
    referencing_pages = [str(page) for page in op.get("referencing_pages", [])]
    for source in op["sources"]:
        source_path = paths.require_raw_path(str(source))
        stat = source_path.stat()
        rel = paths.rel(source_path)
        manifest[rel] = {
            "sha256": _file_hash(source_path),
            "size": stat.st_size,
            "captured_at": datetime.fromtimestamp(
                stat.st_mtime, timezone.utc
            ).isoformat(),
            "referencing_pages": referencing_pages,
            "last_compiled_candidate_id": candidate_id,
            "last_applied_at": applied_at,
        }
    return json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _materialize_op_content(
    paths: WikiPaths,
    op: dict[str, Any],
    candidate_id: str,
    applied_at: str,
) -> str:
    """Return final file content for an apply op."""

    if op["op"] in {"write_formal_page", "update_index"}:
        return op["content"]
    if op["op"] == "append_log":
        log_path = paths.require_existing_file("log.md")
        original = log_path.read_text(errors="replace")
        header, entries = _split_header_and_entries(original)
        return header + "\n\n".join([op["entry"].rstrip(), *entries]) + "\n"
    if op["op"] == "update_source_manifest":
        return _render_source_manifest(paths, op, candidate_id, applied_at)
    raise ValueError(f"unsupported candidate op: {op['op']}")


def _replace_text(path: Path, content: str) -> None:
    """Atomically replace a text file with fsync."""

    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def apply_candidate(
    paths: WikiPaths,
    candidate_id: str,
    *,
    approved: bool,
    bundle_id: str | None = None,
    expected_status: str | None = None,
    base_hashes: dict[str, str] | None = None,
    ops: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Apply a reviewed Candidate bundle atomically."""

    if not approved:
        raise PermissionError("candidate approval is required")
    candidate = load_candidate(paths, candidate_id)
    if bundle_id is not None and candidate["bundle_id"] != bundle_id:
        raise ValueError("bundle_id does not match candidate")
    if (
        expected_status is not None
        and candidate["status"] != expected_status
        and not (
            expected_status == "approved"
            and approved
            and candidate["status"] == "pending_review"
        )
    ):
        raise ValueError(
            f"candidate status is {candidate['status']}, expected {expected_status}"
        )
    if candidate["status"] not in {"pending_review", "approved"}:
        raise ValueError(f"candidate cannot be applied from status {candidate['status']}")

    bundle = candidate["bundle"]
    bundle_ops = ops or bundle["ops"]
    if _bundle_hash(bundle_ops) != bundle["content_hash"]:
        raise ValueError("candidate bundle content_hash mismatch")
    effective_base_hashes = base_hashes or candidate["base_hashes"]

    target_paths: list[Path] = []
    applied_at = _now().isoformat()
    materialized: list[tuple[dict[str, Any], Path, str]] = []
    for op in bundle_ops:
        _validate_write_op(paths, op)
        target_path = paths.resolve(op["path"])
        content = _materialize_op_content(paths, op, candidate_id, applied_at)
        content_hash = op.get("content_hash")
        if content_hash and op["op"] != "append_log":
            actual_content_hash = _sha256_bytes(content.encode("utf-8"))
            if actual_content_hash != content_hash:
                raise ValueError(f"content hash mismatch for {op['path']}")
        if target_path in target_paths:
            raise ValueError(f"APPLY_CONFLICT: duplicate target {op['path']}")
        target_paths.append(target_path)
        materialized.append((op, target_path, content))

    lock_path = _lock_path(paths)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    backups: dict[Path, bytes | None] = {}
    applied_paths: list[Path] = []
    rolled_back = False
    with lock_path.open("a+") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            for rel_path, expected_hash in effective_base_hashes.items():
                actual_hash = _file_hash(paths.resolve(rel_path))
                if actual_hash != expected_hash:
                    candidate["status"] = "stale"
                    _atomic_write_json(_candidate_path(paths, candidate_id), candidate)
                    raise RuntimeError(f"STALE_CANDIDATE: {rel_path}")
            for _, target_path, _ in materialized:
                backups[target_path] = (
                    target_path.read_bytes() if target_path.exists() else None
                )
            candidate["status"] = "applying"
            candidate["review"] = {
                "approved_by": "tool_call",
                "approved_at": applied_at,
                "approval_hash": bundle["content_hash"],
            }
            _atomic_write_json(_candidate_path(paths, candidate_id), candidate)
            for _, target_path, content in materialized:
                _replace_text(target_path, content)
                applied_paths.append(target_path)
        except Exception:
            rolled_back = True
            for path in reversed(applied_paths):
                backup = backups[path]
                if backup is None:
                    try:
                        path.unlink()
                    except FileNotFoundError:
                        pass
                else:
                    _replace_text(path, backup.decode("utf-8"))
            if candidate["status"] != "stale":
                candidate["status"] = "failed"
            _atomic_write_json(_candidate_path(paths, candidate_id), candidate)
            raise
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    candidate["status"] = "applied"
    _atomic_write_json(_candidate_path(paths, candidate_id), candidate)
    return {
        "candidate_id": candidate_id,
        "bundle_id": candidate["bundle_id"],
        "applied_ops": len(materialized),
        "new_hashes": {
            paths.rel(target_path): _file_hash(target_path)
            for _, target_path, _ in materialized
        },
        "transaction": {
            "atomic": True,
            "rolled_back": rolled_back,
        },
    }

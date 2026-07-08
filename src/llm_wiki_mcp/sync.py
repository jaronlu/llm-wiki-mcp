"""Formal page sync helpers for controlled domain upserts."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

from .paths import WikiPathError, WikiPaths
from .responses import response_envelope

PAGE_TYPE_DIRS = {
    "concept": "concepts",
    "query": "queries",
    "comparison": "comparisons",
    "summary": "summaries",
    "reference": "references",
}


def _validate_segment(value: str, label: str) -> str:
    """Validate a single path segment used to build a domain path."""

    normalized = value.strip()
    if (
        not normalized
        or normalized in {".", ".."}
        or "/" in normalized
        or "\\" in normalized
        or ":" in normalized
    ):
        raise WikiPathError(f"{label} must be a single relative path segment")
    return normalized


def _markdown_name(file_name: str) -> str:
    """Normalize a caller-provided file name/path to a markdown target."""

    normalized = file_name.strip()
    if not normalized:
        raise ValueError("fileName must not be empty")
    if Path(normalized).is_absolute():
        raise WikiPathError("fileName must be relative")
    candidate = Path(normalized)
    if any(part in {"", ".", ".."} for part in candidate.parts):
        raise WikiPathError("fileName must not contain empty or parent path segments")
    if candidate.suffix and candidate.suffix != ".md":
        raise WikiPathError("fileName must be a markdown file")
    if not candidate.suffix:
        candidate = Path(f"{normalized}.md")
    return candidate.as_posix()


def _is_under(path: Path, root: Path) -> bool:
    """Return whether path is root or under root after resolution."""

    return path == root or root in path.parents


def _domain_root(paths: WikiPaths, domain: str) -> Path:
    """Return the formal domain root for a domain name."""

    domain_name = _validate_segment(domain, "domain")
    root = paths.resolve(Path("domains") / domain_name)
    if "domains" not in paths.formal_dirs:
        raise WikiPathError("domains is not configured as a formal directory")
    return root


def _find_existing(paths: WikiPaths, domain_root: Path, file_name: str) -> Path | None:
    """Find an existing file by path or basename inside a domain."""

    if "/" in file_name:
        candidate = paths.resolve(domain_root / file_name)
        if not _is_under(candidate, domain_root):
            raise WikiPathError("fileName must stay under the selected domain")
        return candidate if candidate.is_file() else None

    if not domain_root.exists():
        return None
    matches = sorted(path for path in domain_root.rglob(file_name) if path.is_file())
    if len(matches) > 1:
        rels = ", ".join(paths.rel(path) for path in matches)
        raise ValueError(f"multiple pages named {file_name} in domain: {rels}")
    return matches[0] if matches else None


def _new_path(
    paths: WikiPaths, domain_root: Path, file_name: str, page_type: str
) -> Path:
    """Return the create path for a missing domain page."""

    if "/" in file_name:
        candidate = paths.resolve(domain_root / file_name)
    else:
        type_dir = PAGE_TYPE_DIRS.get(page_type, f"{page_type}s")
        candidate = paths.resolve(domain_root / type_dir / file_name)
    if not _is_under(candidate, domain_root):
        raise WikiPathError("fileName must stay under the selected domain")
    if not paths.is_formal_page(candidate):
        raise WikiPathError("sync target must be under configured formal_dirs")
    return candidate


def _atomic_write_text(path: Path, content: str) -> None:
    """Atomically replace a text file with UTF-8 content."""

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


def sync_domain_file(
    paths: WikiPaths,
    *,
    fileName: str,
    content: str,
    domain: str = "general",
    page_type: str = "concept",
) -> dict[str, Any]:
    """Create or update a formal page in domains/<domain> by fileName."""

    if page_type == "entity":
        raise ValueError("sync only targets domains/<domain>; entity is not supported")
    file_name = _markdown_name(fileName)
    domain_path = _domain_root(paths, domain)
    existing = _find_existing(paths, domain_path, file_name)
    target = existing or _new_path(paths, domain_path, file_name, page_type)
    rel = paths.rel(target)
    if target.suffix != ".md":
        raise WikiPathError(f"sync target must be markdown: {rel}")

    before_bytes = target.stat().st_size if target.exists() else 0
    _atomic_write_text(target, content)
    action = "updated" if existing else "created"
    encoded = content.encode("utf-8")
    return {
        **response_envelope(would_write=True, next_action="append_log"),
        "action": action,
        "created": action == "created",
        "updated": action == "updated",
        "path": rel,
        "domain": domain,
        "fileName": fileName,
        "bytes": len(encoded),
        "previous_bytes": before_bytes,
    }

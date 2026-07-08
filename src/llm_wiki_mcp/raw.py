"""Read and create immutable raw source documents under `raw/`."""

from __future__ import annotations

import os
import tempfile
from datetime import datetime, timezone
from typing import Any

from .content import DEFAULT_CONTENT_LIMIT, slice_content
from .paths import WikiPathError, WikiPaths


def _fsync_directory(path: str) -> None:
    """Best-effort fsync for a directory after atomic filesystem updates."""

    try:
        dir_fd = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)


def read_raw_source(
    paths: WikiPaths,
    path: str,
    offset: int = 0,
    limit: int = DEFAULT_CONTENT_LIMIT,
) -> dict[str, Any]:
    """Read a raw source file with pagination metadata and immutable marker."""

    file_path = paths.require_raw_path(path)
    if not file_path.is_file():
        raise FileNotFoundError(f"File not found: {paths.rel(file_path)}")
    sliced = slice_content(file_path.read_text(errors="replace"), offset=offset, limit=limit)
    return {
        "path": paths.rel(file_path),
        **sliced,
        "immutable": True,
    }


def create_raw_source(paths: WikiPaths, path: str, content: str) -> dict[str, Any]:
    """Create a raw source atomically without overwriting existing files."""

    file_path = paths.require_raw_path(path)
    rel = paths.rel(file_path)
    if not rel.endswith(".md"):
        raise WikiPathError(f"raw source must be a markdown file: {rel}")

    file_path.parent.mkdir(parents=True, exist_ok=True)
    encoded = content.encode("utf-8")
    fd, tmp_name = tempfile.mkstemp(prefix=f".{file_path.name}.", dir=file_path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(tmp_name, file_path)
        except FileExistsError as exc:
            raise FileExistsError(f"raw source already exists: {rel}") from exc
        _fsync_directory(str(file_path.parent))
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)

    return {
        "created": True,
        "path": rel,
        "bytes": len(encoded),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

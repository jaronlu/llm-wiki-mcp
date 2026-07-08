from __future__ import annotations

import os
import tempfile
from typing import Any

from .paths import WikiPathError, WikiPaths


def read_raw_source(paths: WikiPaths, path: str) -> dict[str, Any]:
    file_path = paths.require_under(path, "raw")
    if not file_path.is_file():
        raise FileNotFoundError(f"File not found: {paths.rel(file_path)}")
    return {
        "path": paths.rel(file_path),
        "content": file_path.read_text(errors="replace"),
        "immutable": True,
    }


def create_raw_source(
    paths: WikiPaths,
    path: str,
    content: str,
    allow_overwrite: bool = False,
) -> dict[str, Any]:
    file_path = paths.require_under(path, "raw")
    rel = paths.rel(file_path)
    if not rel.endswith(".md"):
        raise WikiPathError(f"raw source must be a markdown file: {rel}")
    existed_before = file_path.exists()
    if existed_before and not allow_overwrite:
        raise FileExistsError(f"raw source already exists: {rel}")

    file_path.parent.mkdir(parents=True, exist_ok=True)
    encoded = content.encode("utf-8")
    fd, tmp_name = tempfile.mkstemp(prefix=f".{file_path.name}.", dir=file_path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, file_path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)

    return {"created": True, "path": rel, "bytes": len(encoded), "overwritten": existed_before}

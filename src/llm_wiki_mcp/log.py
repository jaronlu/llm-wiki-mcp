"""Structured rolling updates for `log.md`."""

from __future__ import annotations

import fcntl
import os
import tempfile
from dataclasses import dataclass
from datetime import date as local_date
from pathlib import Path
from typing import Any

from .paths import WikiPaths
from .responses import candidate_envelope, response_envelope


@dataclass(frozen=True)
class LogEntry:
    """Structured fields required for a single llm-wiki log entry."""

    action: str
    subject: str
    reason: str
    changes: str
    impact: str
    verification: str
    entry_date: str | None = None

    def render(self) -> str:
        """Render the entry in the repository's markdown log format."""

        when = self.entry_date or local_date.today().isoformat()
        return "\n".join(
            [
                f"## [{when}] {self.action} | {self.subject}",
                f"- 原因: {self.reason}",
                f"- 更新: {self.changes}",
                f"- 影响: {self.impact}",
                f"- 验证: {self.verification}",
                "",
            ]
        )


def _fsync_directory(path: Path) -> None:
    """Best-effort fsync for a directory after replacing a file inside it."""

    try:
        dir_fd = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)


def _atomic_write_text(path: Path, content: str) -> None:
    """Atomically replace a text file using temp-write, fsync, and rename."""

    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
        _fsync_directory(path.parent)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def _split_header_and_entries(text: str) -> tuple[str, list[str]]:
    """Split log.md into its static header and individual dated entries."""

    lines = text.splitlines()
    first_entry = next(
        (idx for idx, line in enumerate(lines) if line.startswith("## [")), len(lines)
    )
    header = "\n".join(lines[:first_entry]).rstrip() + "\n\n"
    rest = "\n".join(lines[first_entry:]).strip()
    if not rest:
        return header, []

    entries: list[str] = []
    current: list[str] = []
    for line in rest.splitlines():
        if line.startswith("## [") and current:
            entries.append("\n".join(current).rstrip())
            current = [line]
        else:
            current.append(line)
    if current:
        entries.append("\n".join(current).rstrip())
    return header, entries


def create_log_candidate(
    action: str,
    subject: str,
    reason: str,
    changes: str,
    impact: str,
    verification: str,
    date: str | None = None,
) -> dict[str, Any]:
    """Render a log.md entry candidate without writing it.

    Unlike append_log, this returns a proposed log entry for caller review.
    Use this when the full review package (page candidate + index candidate +
    log candidate) should be shown to the user before any disk writes.
    """

    entry = LogEntry(
        action=action,
        subject=subject,
        reason=reason,
        changes=changes,
        impact=impact,
        verification=verification,
        entry_date=date,
    )
    return {
        **candidate_envelope(),
        "date": entry.entry_date or local_date.today().isoformat(),
        "action": action,
        "subject": subject,
        "content": entry.render(),
    }


def append_log(
    paths: WikiPaths, entry: LogEntry, retention_entries: int = 120
) -> dict[str, Any]:
    """Append an entry to log.md under an exclusive lock and trim retention."""

    log_path = paths.require_existing_file("log.md")
    lock_path = log_path.with_name(f"{log_path.name}.lock")
    with lock_path.open("a+") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            original = log_path.read_text(errors="replace")
            header, entries = _split_header_and_entries(original)
            rendered = entry.render().rstrip()
            new_entries = [rendered, *entries]
            trimmed_entries = max(0, len(new_entries) - retention_entries)
            kept = new_entries[:retention_entries]
            _atomic_write_text(log_path, header + "\n\n".join(kept) + "\n")
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
    return {
        **response_envelope(would_write=True),
        "updated": True,
        "path": paths.rel(log_path),
        "entry_count": len(kept),
        "trimmed_entries": trimmed_entries,
    }

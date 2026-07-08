from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from .paths import WikiPaths


@dataclass(frozen=True)
class LogEntry:
    action: str
    subject: str
    reason: str
    changes: str
    impact: str
    verification: str
    entry_date: str | None = None

    def render(self) -> str:
        when = self.entry_date or date.today().isoformat()
        return "\n".join([
            f"## [{when}] {self.action} | {self.subject}",
            f"- 原因: {self.reason}",
            f"- 更新: {self.changes}",
            f"- 影响: {self.impact}",
            f"- 验证: {self.verification}",
            "",
        ])


def _split_header_and_entries(text: str) -> tuple[str, list[str]]:
    lines = text.splitlines()
    first_entry = next((idx for idx, line in enumerate(lines) if line.startswith("## [")), len(lines))
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


def append_log(paths: WikiPaths, entry: LogEntry, retention_entries: int = 120) -> dict[str, Any]:
    log_path = paths.require_existing_file("log.md")
    original = log_path.read_text(errors="replace")
    header, entries = _split_header_and_entries(original)
    rendered = entry.render().rstrip()
    new_entries = [rendered, *entries]
    trimmed_entries = max(0, len(new_entries) - retention_entries)
    kept = new_entries[:retention_entries]
    log_path.write_text(header + "\n\n".join(kept) + "\n")
    return {
        "updated": True,
        "path": paths.rel(log_path),
        "entry_count": len(kept),
        "trimmed_entries": trimmed_entries,
    }

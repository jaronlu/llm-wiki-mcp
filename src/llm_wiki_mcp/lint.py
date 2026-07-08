from __future__ import annotations

import re
import subprocess
from typing import Any

from .paths import WikiPaths

SUMMARY_RE = re.compile(r"- (formal pages|catalog pages|errors|warnings): (\d+)")


def run_lint(paths: WikiPaths) -> dict[str, Any]:
    proc = subprocess.run(
        ["python3", "scripts/wiki_lint.py"],
        cwd=paths.root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    output = proc.stdout or ""
    summary: dict[str, int] = {}
    errors: list[str] = []
    warnings: list[str] = []
    section: str | None = None

    for line in output.splitlines():
        match = SUMMARY_RE.search(line)
        if match:
            key = match.group(1).replace(" ", "_")
            summary[key] = int(match.group(2))
            continue
        if line.startswith("ERRORS"):
            section = "errors"
            continue
        if line.startswith("WARNINGS"):
            section = "warnings"
            continue
        if line.startswith("- ") and section == "errors":
            errors.append(line[2:])
        elif line.startswith("- ") and section == "warnings":
            warnings.append(line[2:])

    return {
        "exit_code": proc.returncode,
        "summary": summary,
        "errors": errors,
        "warnings": warnings,
        "raw_output": output,
    }

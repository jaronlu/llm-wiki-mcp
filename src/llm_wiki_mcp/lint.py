"""Wrapper for llm-wiki's repository lint script."""

from __future__ import annotations

import re
import subprocess
from typing import Any

from .paths import WikiPaths

SUMMARY_RE = re.compile(r"- (formal pages|catalog pages|errors|warnings): (\d+)")
DEFAULT_LINT_TIMEOUT_SECONDS = 60.0


def _parse_lint_output(output: str) -> tuple[dict[str, int], list[str], list[str]]:
    """Parse wiki_lint.py stdout into summary, error, and warning sections."""

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
    return summary, errors, warnings


def run_lint(paths: WikiPaths, timeout_seconds: float = DEFAULT_LINT_TIMEOUT_SECONDS) -> dict[str, Any]:
    """Run `scripts/wiki_lint.py` and return non-zero results as structured data."""

    try:
        proc = subprocess.run(
            ["python3", "scripts/wiki_lint.py"],
            cwd=paths.root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        output = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
        message = f"wiki_lint.py timed out after {timeout_seconds:g}s"
        return {
            "exit_code": None,
            "timed_out": True,
            "summary": {},
            "errors": [message],
            "warnings": [],
            "raw_output": output,
        }
    except OSError as exc:
        message = f"failed to run scripts/wiki_lint.py: {exc}"
        return {
            "exit_code": None,
            "timed_out": False,
            "summary": {},
            "errors": [message],
            "warnings": [],
            "raw_output": "",
        }

    output = proc.stdout or ""
    summary, errors, warnings = _parse_lint_output(output)
    return {
        "exit_code": proc.returncode,
        "timed_out": False,
        "summary": summary,
        "errors": errors,
        "warnings": warnings,
        "raw_output": output,
    }

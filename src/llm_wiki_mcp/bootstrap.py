"""Bootstrap and structure inspection tools for open-source llm-wiki projects."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .responses import response_envelope

REQUIRED_FILES = (
    "SCHEMA.md",
    "AGENTS.md",
    "index.md",
    "log.md",
    "_meta/topic-map.md",
    "scripts/wiki_lint.py",
)
REQUIRED_DIRS = ("domains", "entities", "raw", "drafts", "reading", "_meta", "scripts")


def _schema_template(language: str) -> str:
    title = "Wiki Schema" if language == "en" else "Wiki Schema 规范"
    return f"""# {title}

## Directory Structure

- `raw/`: immutable source materials.
- `domains/`: compiled knowledge pages organized by domain and page type.
- `entities/`: cross-domain entities.
- `drafts/` and `reading/`: non-formal zones.

## Frontmatter

```yaml
---
title: Page Title
created: YYYY-MM-DD
updated: YYYY-MM-DD
type: concept | query | comparison | summary | entity | reference
tags: []
sources: []
confidence: high | medium | low
---
```

## Rules

- Keep `raw/` immutable.
- Register every formal page in `index.md`.
- Write every maintenance action to `log.md`.
- Preserve `[[wikilinks]]` in source wiki files.
"""


def _agents_template(language: str) -> str:
    title = "LLM Wiki Agent Guide" if language == "en" else "llm-wiki Agent Guide"
    return f"""# {title}

This is an LLM-maintained wiki. Humans choose sources and ask questions; agents compile durable markdown pages from source evidence.

## Operating Rules

1. Read `SCHEMA.md`, `index.md`, and `log.md` before maintenance.
2. Prefer updating existing pages when a new source strengthens an existing topic.
3. Create a new page only when the topic should be independently recalled.
4. Keep raw sources immutable.
5. Use candidate-first workflows for formal pages, index updates, migration, redaction, and public export.
"""


def _index_template() -> str:
    return "# Knowledge Base Index\n\n"


def _log_template() -> str:
    return (
        "# Wiki Log\n\n"
        "> Rolling recent log. Newest first.\n"
        "> Full history lives in Git.\n"
    )


def _topic_map_template() -> str:
    return "# Topic Map\n\nCurated navigation and learning paths live here.\n"


def _lint_template() -> str:
    return """from pathlib import Path

root = Path(__file__).resolve().parents[1]
formal = list((root / "domains").rglob("*.md")) if (root / "domains").exists() else []
formal += list((root / "entities").rglob("*.md")) if (root / "entities").exists() else []
index = root / "index.md"
log = root / "log.md"
errors = []
if not index.exists():
    errors.append("missing index.md")
if not log.exists():
    errors.append("missing log.md")
print("Wiki lint summary")
print(f"- formal pages: {len(formal)}")
print("- catalog pages: 0")
print(f"- errors: {len(errors)}")
print("- warnings: 0")
for error in errors:
    print(f"ERROR: {error}")
raise SystemExit(1 if errors else 0)
"""


def _template_for(path: str, language: str) -> str:
    templates = {
        "SCHEMA.md": _schema_template(language),
        "AGENTS.md": _agents_template(language),
        "index.md": _index_template(),
        "log.md": _log_template(),
        "_meta/topic-map.md": _topic_map_template(),
        "scripts/wiki_lint.py": _lint_template(),
    }
    return templates[path]


def init_wiki(
    root: str | Path, profile: str = "personal", language: str = "zh"
) -> dict[str, Any]:
    """Create a minimal llm-wiki structure without overwriting existing files."""

    root_path = Path(root).expanduser()
    if root_path.exists() and not root_path.is_dir():
        raise NotADirectoryError(f"wiki root is not a directory: {root_path}")
    root_path.mkdir(parents=True, exist_ok=True)

    created: list[str] = []
    skipped: list[str] = []
    warnings: list[str] = []

    for dirname in REQUIRED_DIRS:
        path = root_path / dirname
        if path.exists():
            skipped.append(dirname)
        else:
            path.mkdir(parents=True)
            created.append(dirname)

    for filename in REQUIRED_FILES:
        path = root_path / filename
        if path.exists():
            skipped.append(filename)
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8") as handle:
            handle.write(_template_for(filename, language))
        created.append(filename)

    if profile not in {"personal", "research", "engineering", "learning", "default"}:
        warnings.append(f"unknown profile '{profile}', used generic templates")

    return {
        **response_envelope(
            would_write=bool(created),
            warnings=warnings,
            next_action="inspect_wiki",
        ),
        "initialized": True,
        "root": str(root_path),
        "profile": profile,
        "language": language,
        "created": created,
        "skipped": skipped,
    }


def inspect_wiki(root: str | Path) -> dict[str, Any]:
    """Inspect whether a directory has the minimal llm-wiki structure."""

    root_path = Path(root).expanduser()
    missing: list[str] = []
    if not root_path.exists() or not root_path.is_dir():
        missing = [*REQUIRED_FILES, *REQUIRED_DIRS]
        return {
            **response_envelope(next_action="run init_wiki"),
            "is_wiki": False,
            "root": str(root_path),
            "missing": missing,
            "detected": {"markdown_files": 0, "formal_pages": 0, "raw_sources": 0},
        }

    for item in REQUIRED_FILES:
        if not (root_path / item).is_file():
            missing.append(item)
    for item in REQUIRED_DIRS:
        if not (root_path / item).is_dir():
            missing.append(item)

    markdown_files = list(root_path.rglob("*.md"))
    formal_pages: list[Path] = []
    for dirname in ("domains", "entities"):
        base = root_path / dirname
        if base.exists():
            formal_pages.extend(base.rglob("*.md"))
    raw_sources = (
        list((root_path / "raw").rglob("*.md")) if (root_path / "raw").exists() else []
    )

    return {
        **response_envelope(next_action="ready" if not missing else "run init_wiki"),
        "is_wiki": not missing,
        "root": str(root_path),
        "missing": missing,
        "detected": {
            "markdown_files": len(markdown_files),
            "formal_pages": len(formal_pages),
            "raw_sources": len(raw_sources),
        },
    }

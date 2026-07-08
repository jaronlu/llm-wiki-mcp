"""Configuration loading for the llm-wiki MCP server."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

DEFAULT_WIKI_ROOT = Path.home() / "llm-wiki"


@dataclass(frozen=True)
class Config:
    """Runtime configuration and permission switches for the MCP server."""

    wiki_root: Path = DEFAULT_WIKI_ROOT
    allow_write_raw: bool = True
    allow_write_formal: bool = False
    allow_update_index: bool = False
    allow_modify_schema: bool = False
    log_retention_entries: int = 120
    formal_dirs: tuple[str, ...] = ("domains", "entities")
    raw_dirs: tuple[str, ...] = ("raw",)
    non_formal_dirs: tuple[str, ...] = ("drafts", "reading")


def _as_bool(value: Any, default: bool) -> bool:
    """Coerce YAML/env values into booleans while preserving a default for nulls."""

    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def _as_tuple(value: Any, default: tuple[str, ...]) -> tuple[str, ...]:
    """Coerce a YAML scalar/list into a tuple of strings."""

    if value is None:
        return default
    if isinstance(value, str):
        return (value,)
    if isinstance(value, list):
        return tuple(str(item) for item in value if str(item).strip())
    return default


def load_config(config_path: str | Path | None = None) -> Config:
    """Load config from defaults, optional YAML, then environment overrides."""

    data: dict[str, Any] = {}
    path_value = config_path or os.environ.get("LLM_WIKI_MCP_CONFIG")
    if path_value:
        path = Path(path_value).expanduser()
        if path.exists():
            loaded = yaml.safe_load(path.read_text()) or {}
            if not isinstance(loaded, dict):
                raise ValueError(f"Config file must contain a mapping: {path}")
            data.update(loaded)

    wiki_root = Path(os.environ.get("LLM_WIKI_ROOT", data.get("wiki_root", DEFAULT_WIKI_ROOT))).expanduser()
    return Config(
        wiki_root=wiki_root,
        allow_write_raw=_as_bool(data.get("allow_write_raw"), True),
        allow_write_formal=_as_bool(data.get("allow_write_formal"), False),
        allow_update_index=_as_bool(data.get("allow_update_index"), False),
        allow_modify_schema=_as_bool(data.get("allow_modify_schema"), False),
        log_retention_entries=int(data.get("log_retention_entries", 120)),
        formal_dirs=_as_tuple(data.get("formal_dirs"), ("domains", "entities")),
        raw_dirs=_as_tuple(data.get("raw_dirs"), ("raw",)),
        non_formal_dirs=_as_tuple(data.get("non_formal_dirs"), ("drafts", "reading")),
    )

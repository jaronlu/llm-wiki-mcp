"""Configuration loading for the llm-wiki MCP server."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

# Used only when neither YAML config nor environment variables provide a root.
FALLBACK_WIKI_ROOT = Path.home() / "llm-wiki"
LOCAL_CONFIG_PATHS = (Path("config/config.yaml"), Path("config.yaml"))
CONFIG_KEYS = {
    "wiki_root",
    "init_wiki_root",
    "allow_write_raw",
    "allow_write_formal",
    "allow_update_index",
    "allow_modify_schema",
    "log_retention_entries",
    "formal_dirs",
    "raw_dirs",
    "non_formal_dirs",
}


@dataclass(frozen=True)
class Config:
    """Runtime configuration and permission switches for the MCP server."""

    wiki_root: Path = FALLBACK_WIKI_ROOT
    init_wiki_root: Path | None = None
    allow_write_raw: bool = False
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


def _as_dir_tuple(value: Any, default: tuple[str, ...], field: str) -> tuple[str, ...]:
    """Coerce and validate top-level wiki directory names."""

    if value is None:
        items = default
    if isinstance(value, str):
        items = (value,)
    elif isinstance(value, list):
        if not all(isinstance(item, str) for item in value):
            raise ValueError(f"{field} must contain only strings")
        items = tuple(value)
    elif value is not None:
        raise ValueError(f"{field} must be a string or list of strings")

    normalized = tuple(item.strip() for item in items)
    if not normalized or any(not item for item in normalized):
        raise ValueError(f"{field} must contain at least one non-empty directory")
    for item in normalized:
        if item in {".", ".."} or "/" in item or "\\" in item or ":" in item:
            raise ValueError(
                f"{field} entries must be top-level relative directories: {item}"
            )
    return normalized


def _as_optional_path(value: Any) -> Path | None:
    """Coerce a YAML/env path into an expanded Path when present."""

    if value is None or str(value).strip() == "":
        return None
    return Path(str(value)).expanduser()


def _as_path(value: Any, default: Path) -> Path:
    """Coerce a YAML/env path into an expanded Path with a non-null default."""

    if value is None or str(value).strip() == "":
        return default
    return Path(str(value)).expanduser()


def _as_positive_int(value: Any, default: int, field: str) -> int:
    """Coerce a YAML/env value into a positive integer."""

    if value is None:
        return default
    if isinstance(value, bool):
        raise ValueError(f"{field} must be a positive integer")
    if isinstance(value, float):
        raise ValueError(f"{field} must be a positive integer")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be a positive integer") from exc
    if parsed <= 0:
        raise ValueError(f"{field} must be a positive integer")
    return parsed


def _resolve_config_path(config_path: str | Path | None = None) -> Path | None:
    """Resolve explicit, environment, or local config path in precedence order."""

    if config_path is not None:
        return Path(config_path).expanduser()
    env_path = os.environ.get("LLM_WIKI_MCP_CONFIG")
    if env_path:
        return Path(env_path).expanduser()
    for path in LOCAL_CONFIG_PATHS:
        if path.exists():
            return path
    return None


def _validate_config_keys(data: dict[str, Any], path: Path) -> None:
    """Reject unknown top-level config fields."""

    unknown = sorted(set(data) - CONFIG_KEYS)
    if unknown:
        joined = ", ".join(unknown)
        raise ValueError(f"Unknown config field(s) in {path}: {joined}")


def load_config(config_path: str | Path | None = None) -> Config:
    """Load config from defaults, optional YAML, then environment overrides."""

    data: dict[str, Any] = {}
    path = _resolve_config_path(config_path)
    if path is not None:
        if path.exists():
            loaded = yaml.safe_load(path.read_text()) or {}
            if not isinstance(loaded, dict):
                raise ValueError(f"Config file must contain a mapping: {path}")
            _validate_config_keys(loaded, path)
            data.update(loaded)

    wiki_root_value = os.environ.get("LLM_WIKI_ROOT") or data.get("wiki_root")
    wiki_root = _as_path(wiki_root_value, FALLBACK_WIKI_ROOT)
    init_wiki_root = _as_optional_path(
        os.environ.get("LLM_WIKI_INIT_ROOT", data.get("init_wiki_root"))
    )
    return Config(
        wiki_root=wiki_root,
        init_wiki_root=init_wiki_root,
        allow_write_raw=_as_bool(data.get("allow_write_raw"), False),
        allow_write_formal=_as_bool(data.get("allow_write_formal"), False),
        allow_update_index=_as_bool(data.get("allow_update_index"), False),
        allow_modify_schema=_as_bool(data.get("allow_modify_schema"), False),
        log_retention_entries=_as_positive_int(
            data.get("log_retention_entries"), 120, "log_retention_entries"
        ),
        formal_dirs=_as_dir_tuple(
            data.get("formal_dirs"), ("domains", "entities"), "formal_dirs"
        ),
        raw_dirs=_as_dir_tuple(data.get("raw_dirs"), ("raw",), "raw_dirs"),
        non_formal_dirs=_as_dir_tuple(
            data.get("non_formal_dirs"), ("drafts", "reading"), "non_formal_dirs"
        ),
    )

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class WikiPathError(ValueError):
    """Raised when a requested path violates the wiki root boundary."""


@dataclass(frozen=True)
class WikiPaths:
    root: Path

    def __post_init__(self) -> None:
        object.__setattr__(self, "root", self.root.expanduser().resolve())

    def resolve(self, path: str | Path) -> Path:
        candidate = Path(path).expanduser()
        if not candidate.is_absolute():
            candidate = self.root / candidate
        resolved = candidate.resolve(strict=False)
        if resolved != self.root and self.root not in resolved.parents:
            raise WikiPathError(f"Path escapes wiki root: {path}")
        return resolved

    def rel(self, path: str | Path) -> str:
        return self.resolve(path).relative_to(self.root).as_posix()

    def require_existing_file(self, path: str | Path) -> Path:
        resolved = self.resolve(path)
        if not resolved.is_file():
            raise FileNotFoundError(f"File not found: {self.rel(resolved)}")
        return resolved

    def require_under(self, path: str | Path, prefix: str) -> Path:
        resolved = self.resolve(path)
        rel = resolved.relative_to(self.root).as_posix()
        clean_prefix = prefix.strip("/") + "/"
        if rel != prefix.strip("/") and not rel.startswith(clean_prefix):
            raise WikiPathError(f"Path must be under {prefix}: {rel}")
        return resolved

    def is_formal_page(self, path: str | Path) -> bool:
        rel = self.rel(path)
        return rel.startswith("domains/") or rel.startswith("entities/")

    def require_formal_page(self, path: str | Path) -> Path:
        resolved = self.resolve(path)
        if not self.is_formal_page(resolved):
            raise WikiPathError(f"Path is not a formal wiki page: {self.rel(resolved)}")
        if resolved.suffix != ".md":
            raise WikiPathError(f"Formal wiki page must be markdown: {self.rel(resolved)}")
        if not resolved.is_file():
            raise FileNotFoundError(f"File not found: {self.rel(resolved)}")
        return resolved

"""Path normalization and root-boundary enforcement for llm-wiki files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class WikiPathError(ValueError):
    """Raised when a requested path violates the wiki root boundary."""


@dataclass(frozen=True)
class WikiPaths:
    """Resolve and validate paths relative to a single llm-wiki root."""

    root: Path
    formal_dirs: tuple[str, ...] = ("domains", "entities")
    raw_dirs: tuple[str, ...] = ("raw",)
    non_formal_dirs: tuple[str, ...] = ("drafts", "reading")

    def __post_init__(self) -> None:
        """Normalize the configured wiki root once at construction time."""

        object.__setattr__(self, "root", self.root.expanduser().resolve())

    def resolve(self, path: str | Path) -> Path:
        """Resolve a user path and reject anything outside the wiki root."""

        candidate = Path(path).expanduser()
        if not candidate.is_absolute():
            candidate = self.root / candidate
        resolved = candidate.resolve(strict=False)
        if resolved != self.root and self.root not in resolved.parents:
            raise WikiPathError(f"Path escapes wiki root: {path}")
        return resolved

    def rel(self, path: str | Path) -> str:
        """Return a root-relative POSIX path after boundary validation."""

        return self.resolve(path).relative_to(self.root).as_posix()

    def markdown_path(self, path: str | Path) -> str | Path:
        """Append `.md` to slug-like paths while leaving explicit suffixes alone."""

        candidate = Path(path)
        if candidate.suffix:
            return path
        return Path(f"{path}.md")

    def require_existing_file(self, path: str | Path) -> Path:
        """Resolve a path and require that it exists as a regular file."""

        resolved = self.resolve(path)
        if not resolved.is_file():
            raise FileNotFoundError(f"File not found: {self.rel(resolved)}")
        return resolved

    def require_under(self, path: str | Path, prefix: str) -> Path:
        """Resolve a path and require that it stays under a wiki subdirectory."""

        resolved = self.resolve(path)
        rel = resolved.relative_to(self.root).as_posix()
        clean_prefix = prefix.strip("/") + "/"
        if rel != prefix.strip("/") and not rel.startswith(clean_prefix):
            raise WikiPathError(f"Path must be under {prefix}: {rel}")
        return resolved

    def require_under_any(self, path: str | Path, prefixes: tuple[str, ...], label: str) -> Path:
        """Resolve a path and require that it stays under one allowed subdirectory."""

        resolved = self.resolve(path)
        rel = resolved.relative_to(self.root).as_posix()
        for prefix in prefixes:
            clean_prefix = prefix.strip("/")
            if rel == clean_prefix or rel.startswith(f"{clean_prefix}/"):
                return resolved
        allowed = ", ".join(prefixes)
        raise WikiPathError(f"Path must be under {label} ({allowed}): {rel}")

    def require_raw_path(self, path: str | Path) -> Path:
        """Resolve a path and require that it belongs to configured raw zones."""

        return self.require_under_any(path, self.raw_dirs, "raw_dirs")

    def is_formal_page(self, path: str | Path) -> bool:
        """Return whether a path belongs to the formal wiki page zones."""

        rel = self.rel(path)
        return any(rel == dirname.strip("/") or rel.startswith(f"{dirname.strip('/')}/") for dirname in self.formal_dirs)

    def require_formal_page(self, path: str | Path) -> Path:
        """Resolve a formal wiki page path or slug and require an existing markdown file."""

        normalized = self.markdown_path(path)
        resolved = self.resolve(normalized)
        if not self.is_formal_page(resolved):
            raise WikiPathError(f"Path is not a formal wiki page: {self.rel(resolved)}")
        if resolved.suffix != ".md":
            raise WikiPathError(f"Formal wiki page must be markdown: {self.rel(resolved)}")
        if not resolved.is_file():
            raise FileNotFoundError(f"File not found: {self.rel(resolved)}")
        return resolved

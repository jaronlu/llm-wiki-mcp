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
    workshop_dirs: tuple[str, ...] = ("workshop",)
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

    def require_under_any(
        self, path: str | Path, prefixes: tuple[str, ...], label: str
    ) -> Path:
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

        resolved = self.resolve(path)
        if not self.is_raw_source(resolved):
            raise WikiPathError(f"Path is not a raw source: {self.rel(resolved)}")
        return resolved

    def _is_workshop_entrypoint(self, relative: str) -> bool:
        """Return whether a relative path is a Workshop project README."""

        parts = Path(relative).parts
        return (
            len(parts) == 3
            and parts[0] in self.workshop_dirs
            and parts[2] == "README.md"
        )

    def _is_workshop_raw(self, relative: str) -> bool:
        """Return whether a relative path belongs to a Workshop raw subtree."""

        parts = Path(relative).parts
        return len(parts) >= 4 and parts[0] in self.workshop_dirs and parts[2] == "raw"

    def is_raw_source(self, path: str | Path) -> bool:
        """Return whether a path belongs to a configured raw source zone."""

        relative = self.rel(path)
        if self._is_workshop_raw(relative):
            return True
        return any(
            relative == dirname.strip("/")
            or relative.startswith(f"{dirname.strip('/')}/")
            for dirname in self.raw_dirs
        )

    def is_formal_page(self, path: str | Path) -> bool:
        """Return whether a path belongs to the formal wiki page zones."""

        rel = self.rel(path)
        return self._is_workshop_entrypoint(rel) or any(
            rel == dirname.strip("/") or rel.startswith(f"{dirname.strip('/')}/")
            for dirname in self.formal_dirs
        )

    def iter_formal_pages(self) -> list[Path]:
        """Return formal markdown pages from standard and Workshop zones."""

        pages: list[Path] = []
        for dirname in self.formal_dirs:
            base = self.root / dirname
            if base.exists():
                pages.extend(base.rglob("*.md"))
        for dirname in self.workshop_dirs:
            base = self.root / dirname
            if not base.exists():
                continue
            for project in base.iterdir():
                entrypoint = project / "README.md"
                if project.is_dir() and entrypoint.is_file():
                    pages.append(entrypoint)
        return sorted(set(pages))

    def iter_raw_sources(self) -> list[Path]:
        """Return raw markdown sources from standard and Workshop zones."""

        sources: list[Path] = []
        for dirname in self.raw_dirs:
            base = self.root / dirname
            if base.exists():
                sources.extend(base.rglob("*.md"))
        for dirname in self.workshop_dirs:
            base = self.root / dirname
            if not base.exists():
                continue
            for raw_dir in base.glob("*/raw"):
                if raw_dir.is_dir():
                    sources.extend(raw_dir.rglob("*.md"))
        return sorted(set(sources))

    def require_formal_page(self, path: str | Path) -> Path:
        """Resolve a formal wiki page path or slug and require an existing markdown file."""

        normalized = self.markdown_path(path)
        resolved = self.resolve(normalized)
        if not self.is_formal_page(resolved):
            raise WikiPathError(f"Path is not a formal wiki page: {self.rel(resolved)}")
        if resolved.suffix != ".md":
            raise WikiPathError(
                f"Formal wiki page must be markdown: {self.rel(resolved)}"
            )
        if not resolved.is_file():
            raise FileNotFoundError(f"File not found: {self.rel(resolved)}")
        return resolved

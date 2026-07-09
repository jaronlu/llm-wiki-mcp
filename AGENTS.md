# Repository Guidelines

## Project Structure & Module Organization

This repository contains a Python MCP server for maintaining local LLM wiki
projects. Runtime code lives in `src/llm_wiki_mcp/`; `server.py` registers MCP
tools, while focused modules such as `raw.py`, `pages.py`, `sync.py`,
`candidates.py`, and `advanced.py` implement tool behavior. Tests live in
`tests/` and mirror the feature areas. Configuration examples live in `config/`.
CI configuration is in `.github/workflows/ci.yml`.

## Architecture & Design Source

Use [docs/design.md](docs/design.md) as the design entrypoint. It links to the
personal wiki design draft when the local symlink target is available. This repo
uses design-driven coding: for tool, permission, workflow, or data-shape changes,
read the spec before editing code. If the spec is wrong or incomplete, update it
first, then implement code and tests to match it.

## Build, Test, and Development Commands

Use `uv` for this project.

```bash
uv sync --dev
uv run llm-wiki-mcp
uv run ruff check .
uv run pytest
```

`uv sync --dev` installs runtime and development dependencies. `uv run
llm-wiki-mcp` starts the MCP server over stdio. `ruff check` runs linting.
`pytest` runs the full test suite.

## Coding Style & Naming Conventions

Target Python 3.11+. Keep modules small and behavior-oriented. Prefer explicit
helper functions over broad utility layers. Use snake_case for functions,
modules, and test names; use PascalCase for dataclasses and exceptions. Keep
tool return values structured, JSON-serializable, and consistent with
`responses.py`. Do not add dependencies unless the standard library or existing
dependencies cannot reasonably solve the problem.

## Testing Guidelines

Tests use `pytest`. Add focused tests for every tool helper and update
`tests/test_server_tools.py` when adding or changing public MCP tools. Name tests
as `test_<behavior>`. Prefer behavior assertions over implementation details.
Run `uv run pytest` and `uv run ruff check .` before committing.

## Commit & Pull Request Guidelines

History uses Conventional Commit style, for example `feat: add domain file sync
tool` and `fix: align MCP tools with design spec`. Keep commits atomic and use
the smallest accurate type: `feat`, `fix`, `docs`, `test`, `refactor`, or
`chore`. Pull requests should describe the behavior change, mention tests run,
and link related issues when applicable.

## Security & Configuration Tips

Keep defaults safe for open-source users. Do not hardcode personal paths,
company names, secrets, private project names, or local-only assumptions. Raw
writes must remain create-only. Formal page writes require explicit
`allow_write_formal: true`; index updates and public exports should stay
candidate-first unless a design update says otherwise.

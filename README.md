# llm-wiki-mcp

MCP server for maintaining a local LLM wiki: immutable `raw/` sources,
candidate-first formal pages, index updates, logs, lint, and governance tools.

The server is designed for personal or team knowledge bases where agents should
help organize knowledge without getting broad, unsafe filesystem write access.

![LLM Wiki MCP workflow example](docs/assets/llm-wiki-exc.png)

## Workflow

```text
New / revised source added
        ↓
compile_page or create_update_candidate
        ↓
Review Candidate bundle
        ↓
apply_candidate after explicit approval
        ↓
run_lint
```

Compile and update workflows return persisted Candidate bundles first, so humans
can review page, index, public-draft, log, and source-manifest changes before
anything touches the formal wiki.

## Quick Start

```bash
uv sync --dev
cp config/examples.config.yaml config/config.yaml
uv run llm-wiki-mcp
```

Edit `config/config.yaml` for your machine. Keep that file local and untracked.

```yaml
wiki_root: ~/llm-wiki
allow_write_raw: false
allow_write_formal: false
allow_update_index: false
allow_modify_schema: false
log_retention_entries: 120
formal_dirs: [domains, entities]
raw_dirs: [raw]
non_formal_dirs: [drafts, reading]
```

## MCP Host Config

Local development mode:

```toml
[mcp_servers.llm_wiki]
command = "uv"
args = ["--directory", "/path/to/llm-wiki-mcp", "run", "llm-wiki-mcp"]
startup_timeout_sec = 120
```

The server always reads configuration from `<repo>/config/config.yaml`; no MCP host environment variable is needed.

## MCP tools

Public tools:

- `init_wiki`
- `inspect_wiki`
- `search_wiki`
- `read_page`
- `read_raw_source`
- `create_raw_source`
- `append_log`
- `compile_page`
- `create_update_candidate`
- `apply_candidate`
- `run_lint`
- `knowledge_health_review`
- `write_public_draft`
- `validate_public_safety`

Mutation tools are conservative by default. Raw writes are disabled unless
`allow_write_raw: true`; applying Candidate bundles is disabled unless
`allow_write_formal: true`; public exports stay candidate-first.

## Configuration

Config loading order:

1. Built-in defaults.
2. Project-local `config/config.yaml`, when present.

The server intentionally ignores MCP host config path environment variables and root override environment variables, so the runtime source of truth stays in the repository-local config file.

Config validation rejects unknown top-level fields, nested directory names,
empty directory lists, and non-positive `log_retention_entries` values.

## Safety Boundaries

- All paths must resolve under `wiki_root`.
- `init_wiki` creates or completes `wiki_root` by default when no explicit
  `root` argument is provided.
- `raw/` writes are create-only and never overwrite existing files.
- Formal page writes require `allow_write_formal: true`; `index.md` updates,
  migrations, and public exports are candidate-first.
- `.llm-wiki/source-manifest.json` tracks raw source digests without modifying
  page frontmatter.
- `run_lint` returns structured lint data instead of treating lint failures as
  MCP transport failures.

## Development

```bash
uv run ruff check .
uv run pytest
```

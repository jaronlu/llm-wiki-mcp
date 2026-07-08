# llm-wiki-mcp

MCP server for maintaining a local LLM wiki: immutable `raw/` sources,
candidate-first formal pages, index updates, logs, lint, and governance tools.

The server is designed for personal or team knowledge bases where agents should
help organize knowledge without getting broad, unsafe filesystem write access.

## Workflow

```text
New / revised source added
        ↓
detect_new_source
        ↓
find_referencing_pages
        │
        ├── 0 pages
        │       ↓
        │ create_formal_page_candidate
        │
        ├── 1 page
        │       ↓
        │ create_update_candidate
        │
        └── N pages
                ↓
        create_update_candidate per affected page
                ↓
Review candidate(s) as a bundle
                ↓
Apply outside this server after explicit approval
                ↓
update_source_manifest
                ↓
append_log
                ↓
run_lint
```

Most maintenance tools return candidates first (`would_write=false`), so humans
can review page, index, public-draft, and log changes before anything touches
the wiki.

## Quick Start

```bash
uv sync --dev
cp config/examples.config.yaml config/config.yaml
uv run llm-wiki-mcp
```

Edit `config/config.yaml` for your machine. Keep that file local and untracked.

```yaml
wiki_root: ~/llm-wiki
init_wiki_root:
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

[mcp_servers.llm_wiki.env]
LLM_WIKI_MCP_CONFIG = "/path/to/llm-wiki-mcp/config/config.yaml"
```

Single-root override mode:

```toml
[mcp_servers.llm_wiki]
command = "uv"
args = ["--directory", "/path/to/llm-wiki-mcp", "run", "llm-wiki-mcp"]
startup_timeout_sec = 120

[mcp_servers.llm_wiki.env]
LLM_WIKI_ROOT = "/path/to/wiki"
LLM_WIKI_INIT_ROOT = "/path/to/init-wiki"
```

## MCP tools

Bootstrap and reading:

- `init_wiki`
- `inspect_wiki`
- `search_wiki`
- `semantic_search` (local deterministic baseline)
- `read_page`
- `read_raw_source`
- `sync` (requires `allow_write_formal: true`)

Candidate-first maintenance:

- `create_formal_page_candidate`
- `create_update_candidate`
- `update_index_candidate`
- `create_log_candidate`
- `compile_raw_to_formal_draft`
- `write_public_draft`
- `standardize_page_candidate`

Governance:

- `run_lint`
- `validate_frontmatter`
- `validate_public_safety`
- `find_related_pages`
- `suggest_wikilinks`
- `classify_source_candidate`
- `detect_new_source`
- `find_referencing_pages`
- `update_source_manifest`
- `find_uncompiled_sources`
- `find_duplicate_topics`
- `find_stale_pages`
- `find_low_confidence_pages`
- `suggest_merge_candidates`
- `knowledge_health_review`
- `audit_wiki_structure`

Mutation tools are conservative by default. Raw writes are disabled unless
`allow_write_raw: true`; domain file sync is disabled unless
`allow_write_formal: true`; index updates and public exports stay
candidate-first.

## Configuration

Config loading order:

1. Built-in defaults.
2. Local `config/config.yaml`, then root `config.yaml`, when present.
3. YAML file from `LLM_WIKI_MCP_CONFIG`.
4. `LLM_WIKI_ROOT`, overriding `wiki_root`.
5. `LLM_WIKI_INIT_ROOT`, overriding `init_wiki_root`.

Config validation rejects unknown top-level fields, nested directory names,
empty directory lists, and non-positive `log_retention_entries` values.

## Safety Boundaries

- All paths must resolve under `wiki_root`.
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

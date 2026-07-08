# llm-wiki-mcp

MCP server for bootstrapping, maintaining, and safely governing Karpathy-style LLM wikis.

An LLM Wiki keeps immutable source material in `raw/`, compiles durable knowledge pages into formal wiki directories, and lets agents query/maintain the wiki through structured tools instead of raw filesystem access.

## Core use cases

1. **Start from zero** — initialize a minimal wiki structure with `init_wiki`.
2. **Maintain an existing wiki** — inspect structure, search pages, create candidates, update logs, and run lint.
3. **Keep the open-source repo clean** — default config, docs, examples, and tests use placeholders instead of private local paths or personal data.

## MCP tools

### Bootstrap

- `init_wiki` — create a minimal wiki structure without overwriting by default.
- `inspect_wiki` — inspect whether a directory has the minimum llm-wiki structure.

### Core operations

- `search_wiki` — search formal wiki pages and/or raw sources with metadata and score.
- `read_page` — read a formal page and parse frontmatter.
- `read_raw_source` — read immutable source material under `raw/`.
- `create_raw_source` — create a new raw source; existing files are never overwritten.
- `append_log` — write a structured rolling `log.md` entry and trim old entries.
- `run_lint` — run `python3 scripts/wiki_lint.py` and return structured results.

### Candidate tools

- `validate_frontmatter` — validate required formal-page frontmatter fields.
- `find_related_pages` — find formal pages related to a page or free-text query.
- `create_formal_page_candidate` — render a formal page candidate without writing it.
- `create_update_candidate` — render an update candidate for an existing formal page without writing it.
- `update_index_candidate` — render an `index.md` update candidate without writing it.
- `create_log_candidate` — render a `log.md` entry candidate without writing it.

## Development

```bash
uv sync --dev
uv run pytest
uv run llm-wiki-mcp
```

## Configuration

Set `LLM_WIKI_MCP_CONFIG=/path/to/llm-wiki.yaml` or `LLM_WIKI_ROOT=/path/to/wiki`.

Example config:

```yaml
wiki_root: ~/llm-wiki
allow_write_raw: true
allow_write_formal: false
allow_update_index: false
allow_modify_schema: false
log_retention_entries: 120
formal_dirs: [domains, entities]
raw_dirs: [raw]
non_formal_dirs: [drafts, reading]
```

Use placeholders in shared docs/configs. Keep private paths, company names, and personal material in local untracked config files.

## Hermes config example

Installed package / tool mode:

```yaml
mcp_servers:
  llm_wiki:
    command: "uvx"
    args:
      - "llm-wiki-mcp"
    env:
      LLM_WIKI_MCP_CONFIG: "/path/to/llm-wiki.yaml"
    timeout: 120
    connect_timeout: 60
```

Local development mode:

```yaml
mcp_servers:
  llm_wiki:
    command: "uv"
    args:
      - "--directory"
      - "/path/to/llm-wiki-mcp"
      - "run"
      - "llm-wiki-mcp"
    env:
      LLM_WIKI_ROOT: "/path/to/wiki"
    timeout: 120
    connect_timeout: 60
```

## Safety boundaries

- All paths must resolve under `wiki_root`.
- `raw/` writes are strictly create-only; existing raw files are never overwritten.
- Formal page writes, `index.md` updates, migration, and public export are candidate-first.
- Shared docs/examples use placeholders; private local config should stay untracked.
- `run_lint` returns lint errors as structured data instead of treating non-zero lint exit as MCP transport failure.

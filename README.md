# llm-wiki-mcp

MCP server for safe, structured access to `~/llm-wiki`.

The server exposes a small P0/P1 toolset:

- `search_wiki` — search formal wiki pages and/or raw sources with metadata.
- `read_page` — read a formal page and parse frontmatter.
- `read_raw_source` — read immutable source material under `raw/`.
- `create_raw_source` — create a new raw source; existing files are never overwritten.
- `append_log` — write a structured rolling `log.md` entry and trim old entries.
- `validate_frontmatter` — validate required formal-page frontmatter fields.
- `find_related_pages` — find formal pages related to a page or free-text query.
- `run_lint` — run `python3 scripts/wiki_lint.py` and return structured results.

## Development

```bash
uv sync --dev
uv run pytest
uv run llm-wiki-mcp
```

## Configuration

Defaults target Jaron's local wiki:

```yaml
wiki_root:***REMOVED***
allow_write_raw: true
allow_write_formal: false
allow_update_index: false
allow_modify_schema: false
log_retention_entries: 120
```

Set `LLM_WIKI_MCP_CONFIG=/path/to/config.yaml` or `LLM_WIKI_ROOT=/path/to/wiki`.

## Hermes config example

```yaml
mcp_servers:
  llm_wiki:
    command: "uv"
    args:
      - "--directory"
      - "PROJECT_ROOT"
      - "run"
      - "llm-wiki-mcp"
    timeout: 120
    connect_timeout: 60
```

## Safety boundaries

- All paths must resolve under `wiki_root`.
- `raw/` writes are strictly create-only; existing raw files are never overwritten.
- Formal page writes, `index.md` updates, and schema modifications are intentionally not implemented in P0.
- `run_lint` returns lint errors as structured data instead of treating non-zero lint exit as MCP transport failure.

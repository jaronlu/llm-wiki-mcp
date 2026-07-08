# llm-wiki-mcp

MCP server for bootstrapping, maintaining, and safely governing Karpathy-style LLM wikis.

An LLM Wiki keeps immutable source material in `raw/`, compiles durable knowledge pages into formal wiki directories, and lets agents query/maintain the wiki through structured tools instead of raw filesystem access.

## Core use cases

1. **Start from zero** — initialize a minimal wiki structure with `init_wiki`.
2. **Maintain an existing wiki** — inspect structure, search pages, create candidates, update logs, and run lint.
3. **Govern long-running knowledge** — detect new sources, review stale or duplicate topics, and generate health reports.
4. **Keep the open-source repo clean** — default config, docs, examples, and tests use placeholders instead of private local paths or personal data.

## MCP tools

### Bootstrap

- `init_wiki` — create a minimal wiki structure without overwriting by default.
- `inspect_wiki` — inspect whether a directory has the minimum llm-wiki structure.

### Core operations

- `search_wiki` — search formal wiki pages and/or raw sources with metadata and score.
- `read_page` — read a formal page, frontmatter, wikilinks, and backlinks.
- `read_raw_source` — read immutable source material under `raw/`.
- `create_raw_source` — create a new raw source; existing files are never overwritten.
- `append_log` — write a structured rolling `log.md` entry and trim old entries.
- `run_lint` — run `python3 scripts/wiki_lint.py` and return structured results.

### Candidate tools

- `validate_frontmatter` — validate required formal-page frontmatter fields.
- `find_related_pages` — find formal pages related to a topic and optional domain.
- `create_formal_page_candidate` — render a formal page candidate without writing it.
- `create_update_candidate` — render an update candidate for an existing formal page without writing it.
- `update_index_candidate` — render an `index.md` update candidate without writing it.
- `create_log_candidate` — render a `log.md` entry candidate without writing it.

### Lifecycle and retrieval

- `semantic_search` — search formal/raw chunks with a deterministic local token-vector baseline.
- `classify_source_candidate` — classify a raw source as raw, draft, formal candidate, update existing, or ignore.
- `compile_raw_to_formal_draft` — compile one raw source into a reviewable formal-page draft.
- `suggest_wikilinks` — suggest formal-page wikilinks for candidate content.

### Source manifests and incremental updates

- `detect_new_source` — detect raw sources that are new or changed since the sidecar manifest.
- `find_referencing_pages` — find formal pages that cite a raw source in `sources`.
- `update_source_manifest` — update `.llm-wiki/source-manifest.json` without modifying page frontmatter.

### Public draft safety

- `write_public_draft` — clean frontmatter and wikilinks into a public-site draft candidate without publishing.
- `validate_public_safety` — check public candidate content for private paths, secrets, interview/salary material, and raw references.

### Long-term governance

- `find_uncompiled_sources` — find raw sources not referenced by formal pages.
- `find_duplicate_topics` — find overlapping formal topics.
- `find_stale_pages` — find old pages or pages mentioning deprecated/removed APIs.
- `find_low_confidence_pages` — find pages marked `confidence: low`.
- `suggest_merge_candidates` — propose merge candidates without deleting or rewriting pages.
- `knowledge_health_review` — summarize lint, uncompiled sources, duplicates, stale pages, and low-confidence pages.
- `audit_wiki_structure` — audit structure and standardization gaps without writing.
- `standardize_page_candidate` — render a frontmatter-standardized page candidate without writing.

## Development

```bash
uv sync --dev
uv run pytest
uv run llm-wiki-mcp
```

## Configuration

The server is configuration-first. Do not hardcode private wiki paths in source code, docs, tests, or shared examples.

Recommended local setup:

```bash
cp config/examples.config.yaml config/config.yaml
```

Then edit `config/config.yaml` for your machine:

- `wiki_root`: the wiki that search, read, lint, and governance tools operate on.
- `init_wiki_root`: optional default target for `init_wiki` when the tool call does not pass `root`.
- `allow_write_raw`: set to `true` only if this MCP host may create new immutable raw sources.
- `formal_dirs`, `raw_dirs`, `non_formal_dirs`: top-level directory names for your wiki layout.
- `sensitive`: optional public-draft safety patterns and terms.

`config/config.yaml` is ignored by Git. Commit `config/examples.config.yaml`; keep real local paths and private rules in `config/config.yaml`.

Configuration precedence:

1. Built-in defaults.
2. Local `config/config.yaml`, then root `config.yaml`, when present.
3. YAML file from `LLM_WIKI_MCP_CONFIG`, which overrides local config discovery.
4. `LLM_WIKI_ROOT`, which overrides `wiki_root` from YAML.
5. `LLM_WIKI_INIT_ROOT`, which overrides `init_wiki_root` from YAML.

Local development with `uv --directory /path/to/llm-wiki-mcp run llm-wiki-mcp` automatically reads `/path/to/llm-wiki-mcp/config/config.yaml` when it exists. For installed package or `uvx` usage, set `LLM_WIKI_MCP_CONFIG=/path/to/config.yaml` explicitly. `init_wiki` also accepts a `root` tool argument; when omitted, it uses `init_wiki_root` first and then falls back to `wiki_root`.

Example config:

```yaml
wiki_root: ~/llm-wiki
init_wiki_root: /private/tmp/llm-wiki-mcp-smoke
allow_write_raw: false
allow_write_formal: false
allow_update_index: false
allow_modify_schema: false
log_retention_entries: 120
formal_dirs: [domains, entities]
raw_dirs: [raw]
non_formal_dirs: [drafts, reading]
```

The same structure is available in `config/examples.config.yaml`.

Use placeholders in shared docs/configs. Keep private paths, company names, and personal material in local untracked config files such as `config/config.yaml`.

Set `allow_write_raw: true` only for trusted local hosts that should be able to create new immutable raw sources. Formal pages, index updates, and public exports remain candidate-first.

`wiki_root` is the active wiki used by search/read/lint tools. `init_wiki_root` is only the default bootstrap target for `init_wiki` when the caller does not pass a `root` argument.

## Codex config example

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
LLM_WIKI_INIT_ROOT = "/private/tmp/llm-wiki-mcp-smoke"
```

## Hermes config example

Installed package / tool mode:

```yaml
mcp_servers:
  llm_wiki:
    command: "uvx"
    args:
      - "llm-wiki-mcp"
    env:
      LLM_WIKI_MCP_CONFIG: "/path/to/llm-wiki-mcp/config/config.yaml"
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
      LLM_WIKI_MCP_CONFIG: "/path/to/llm-wiki-mcp/config/config.yaml"
    timeout: 120
    connect_timeout: 60
```

## Safety boundaries

- All paths must resolve under `wiki_root`.
- Raw writes are disabled by default. When explicitly enabled, `raw/` writes are strictly create-only and existing raw files are never overwritten.
- Formal page writes, `index.md` updates, migration, and public export are candidate-first.
- Source digest tracking uses `.llm-wiki/source-manifest.json`; it does not modify formal page frontmatter.
- Shared docs/examples use placeholders; private local config should stay untracked.
- `run_lint` returns lint errors as structured data instead of treating non-zero lint exit as MCP transport failure.

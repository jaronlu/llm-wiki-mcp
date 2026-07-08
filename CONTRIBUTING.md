# Contributing

Thanks for improving `llm-wiki-mcp`.

## Development Setup

```bash
uv sync --dev
uv run pytest
uv run ruff check .
```

## Design Rules

- Prefer candidate-first tools for formal pages, index updates, schema changes, migrations, and public exports.
- Keep raw-source writes create-only.
- Keep default configuration safe for first-run open-source users.
- Do not hardcode personal paths, company names, private repository names, tokens, or local-only assumptions.
- Keep tool return values structured and reviewable.

## Adding or Changing Tools

When adding a tool:

1. Register it in `src/llm_wiki_mcp/server.py`.
2. Add focused unit tests for the helper implementation.
3. Add or update a server registration/schema test.
4. Update `README.md` if the tool is public.
5. Prefer returning candidates over writing files unless the operation is explicitly safe and configured.

## Before Opening a Pull Request

Run:

```bash
uv run pytest
uv run ruff check .
```

Check that shared files do not contain private local paths or personal data.

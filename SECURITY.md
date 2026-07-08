# Security Policy

## Supported Versions

Security fixes are handled on the main branch until the project starts publishing versioned releases.

## Reporting a Vulnerability

Please report security issues privately before opening a public issue. Include:

- affected version or commit
- reproduction steps
- expected and actual behavior
- whether any private wiki content, secrets, or filesystem paths were exposed

## Security Boundaries

`llm-wiki-mcp` is designed for local, user-controlled Markdown wikis.

- The server does not require network access for core tools.
- All wiki paths must resolve under `wiki_root`.
- Raw writes are disabled by default.
- When raw writes are enabled, they are create-only and never overwrite existing raw sources.
- Formal pages, index updates, migrations, and public export flows are candidate-first.
- Public safety checks are best-effort pattern checks, not a guarantee that content is safe to publish.

Do not expose this MCP server to untrusted remote clients without an additional authentication and sandboxing layer.

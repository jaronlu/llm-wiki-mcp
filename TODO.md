# TODO

## P0 - Open-source blockers

- [x] Fix `update_index_candidate` heading placement.
  - Problem: passing `References` matches only `## References`, so an existing `### References` section is missed and a new top-level section can be appended at the end of `index.md`.
  - Expected: match Markdown headings by text across heading levels, insert within the matched section, and preserve candidate-only behavior.
- [x] Make default write permissions conservative.
  - Problem: `allow_write_raw` currently defaults to `true`, which is too permissive for a first-run open-source MCP server.
  - Expected: defaults are read/candidate-first; examples explicitly opt in to raw writes.
- [x] Make `init_wiki` default target configurable.
  - Problem: smoke-test bootstrap paths such as `/private/tmp/llm-wiki-mcp-smoke-20260708` should not require hardcoded tool arguments.
  - Expected: `init_wiki` uses explicit tool `root`, then `init_wiki_root`, then `wiki_root`.
- [x] Align public docs with runtime behavior.
  - Problem: README is ahead of what a user may see if an MCP host loads a stale server or partial tool set.
  - Expected: tests verify README-listed tools are registered and examples use placeholders only.
- [x] Add release hygiene files.
  - Expected: `LICENSE`, `CHANGELOG.md`, `SECURITY.md`, `CONTRIBUTING.md`, and CI are present before public release.

## P1 - Quality and maintainability

- [ ] Add config validation for unknown fields, invalid directories, and invalid retention values.
- [ ] Normalize tool response envelopes where practical: `candidate`, `would_write`, `warnings`, `errors`, and `next_action`.
- [ ] Add an end-to-end smoke test covering init, inspect, raw create-only, candidates, and lint.
- [ ] Make `run_lint` mode options clear in docs or support `quick` / `full`.

## P2 - Product polish

- [ ] Add a minimal demo wiki fixture for documentation and evaluation.
- [ ] Script the A/B evaluation tasks from `docs/evaluation-plan.md`.
- [ ] Add `uvx llm-wiki-mcp` install instructions after package publishing is ready.

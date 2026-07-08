# Changelog

All notable changes to this project will be documented in this file.

This project follows a lightweight changelog format inspired by Keep a Changelog.

## [Unreleased]

### Added

- Open-source release hygiene files: license, security policy, contribution guide, CI, and project TODO.

### Changed

- Raw-source writes are disabled by default; trusted local deployments can opt in with `allow_write_raw: true`.
- `update_index_candidate` now matches Markdown heading text across heading levels, including nested sections such as `### References`.

### Fixed

- Prevented `update_index_candidate(section_heading="References")` from appending a duplicate top-level `## References` when a nested `### References` section already exists.

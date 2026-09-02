# Public release checklist — v0.2.0

This checklist covers the clean public repository and the external publication
sequence.

## Repository preparation

- [x] Use the public product name `Google Search Console MCP` / `GSC MCP`.
- [x] Use the unique PyPI distribution name `gsc-readonly-mcp`.
- [x] License the release under MIT, copyright Yuliya Murtazina.
- [x] Rename the Python import package to `gsc_mcp`.
- [x] Replace private properties, project IDs, tunnel IDs, and local profile names
      in the release tree with reserved examples.
- [x] Add public installation, security, contribution, and support guidance.
- [x] Add Windows/Linux CI and a PyPI Trusted Publishing workflow.
- [x] Pass lint, automated tests, package build, and clean-install acceptance.
- [x] Pass final current-tree and full-history secret scans.
- [x] Choose a separate clean public history; keep internal project history,
      tags, and acceptance records private.

## External publication gate

Complete these steps in order:

1. Create `muryulia/google-search-console-mcp` as a public repository with one
   reviewed initial commit on `main`.
2. Confirm the public CI matrix and package smoke job.
3. Enable private vulnerability reporting and appropriate default-branch
   protection.
4. Configure the GitHub `pypi` environment.
5. Register a pending PyPI Trusted Publisher for:
   - owner: `muryulia`
   - repository: `google-search-console-mcp`
   - workflow: `publish.yml`
   - environment: `pypi`
   - project: `gsc-readonly-mcp`
6. Create annotated tag `v0.2.0` and publish the GitHub Release. The release
   event starts the trusted PyPI workflow.
7. Verify the PyPI page, hashes, `pipx`/`uvx` installation, console entry point,
   and MCP tool discovery from the published wheel.

The repository name and PyPI project do not need to be identical. The public
title remains Google Search Console MCP.

# Changelog

All notable changes to this project will be documented in this file.
## [0.2.0] - 2026-09-02

### Added

- Public MIT license, contribution guide, security policy, and release checklist.
- Cross-platform GitHub Actions CI for Python 3.10–3.12.
- PyPI Trusted Publishing workflow for the `gsc-readonly-mcp` distribution.
- Public-release regression checks and clean-install documentation.

### Changed

- Renamed the public project to Google Search Console MCP (GSC MCP).
- Renamed the legacy import package to `gsc_mcp` and the console
  command to `gsc-mcp`.
- Generalized all current documentation, examples, test fixtures, and tunnel
  profile names for public self-hosting.

### Security

- Preserved the exact three-tool read-only surface, `webmasters.readonly` scope,
  fixed Google endpoint/method allowlist, verified TLS, and credential-safe
  errors.
- Added private vulnerability-reporting guidance and public-tree identifier
  regression checks.

## [0.1.0] - 2026-09-02

### Added

- Read-only Search Console property discovery.
- Search Analytics queries with named dimensions, filters, and bounded pagination.
- Indexed-state URL Inspection.
- Windows certificate environment support and live STDIO acceptance helper.
- Secure MCP Tunnel profile, health, readiness, and control-plane acceptance.
- ChatGPT development app and Project read acceptance.
- Security, credential-safety, property-identity, and no-write regression tests.

### Security

- Only the `webmasters.readonly` OAuth scope is requested.
- Exactly three read-only tools are exposed.
- Outbound HTTP is restricted to the three official Google read endpoints.
- TLS verification is never disabled and credential-bearing raw errors are not exposed.

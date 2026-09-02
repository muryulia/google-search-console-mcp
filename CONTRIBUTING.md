# Contributing

Thank you for helping improve Google Search Console MCP.

## Scope guardrails

This project is permanently read-only. Pull requests must not add:

- write-capable MCP tools;
- the `webmasters` read/write OAuth scope;
- site or sitemap mutations;
- Google Indexing API calls;
- arbitrary URL fetching or configurable upstream hosts;
- credential, query-row, or page-row logging.

Use `example.com` or another reserved example domain in fixtures and docs. Never
submit credentials, tokens, private Search Console output, or customer URLs.

## Development setup

```console
git clone https://github.com/muryulia/google-search-console-mcp.git
cd google-search-console-mcp
python -m venv .venv
python -m pip install -e ".[dev]"
```

Run the release checks before opening a pull request:

```console
ruff check src tests scripts
pytest
python -m build
```

Changes to tool schemas, auth, networking, TLS, error handling, or pagination
must include regression tests. The exact three-tool inventory and fixed
endpoint/method allowlist are release gates.

## Pull requests

Keep each pull request focused. Explain the user-visible behavior, security
impact, and verification performed. Documentation-only changes should still be
checked for accidental real credentials and non-example properties.

For vulnerabilities, follow `SECURITY.md` instead of opening a public issue.
By contributing, you agree that your contribution is licensed under the MIT
License.

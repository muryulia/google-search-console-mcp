# Google Search Console MCP

**GSC MCP** is a small, security-focused Model Context Protocol server for
first-party Google Search Console data. It exposes property discovery, Search
Analytics, and URL Inspection through the official Google APIs.

The server is structurally read-only: it contains no write tools and requests
only Google's `webmasters.readonly` OAuth scope.

## Tools

| Tool | Purpose | Google request |
|---|---|---|
| `list_sites` | List accessible Search Console properties | `GET /webmasters/v3/sites` |
| `query_search_analytics` | Query clicks, impressions, CTR, position, and dimensions | `POST .../searchAnalytics/query` |
| `inspect_url` | Read the indexed state of a URL | `POST /v1/urlInspection/index:inspect` |

The two `POST` endpoints are read operations. The implementation blocks site,
sitemap, Indexing API, arbitrary HTTP, and all other non-allowlisted requests.
Every tool is annotated with `readOnlyHint=true` and `destructiveHint=false`.

## Requirements

- Python 3.10 or newer
- Google Search Console API enabled for your Google Cloud project
- Application Default Credentials (ADC) with access to the properties you query
- The read-only OAuth scope:
  `https://www.googleapis.com/auth/webmasters.readonly`

Google's Search Console API requires OAuth 2.0 for private user data. Follow the
[official Search Console authorization guide](https://developers.google.com/webmaster-tools/v1/how-tos/authorizing)
and [ADC setup guide](https://docs.cloud.google.com/docs/authentication/provide-credentials-adc).
Keep OAuth client files, service-account keys, ADC files, and tokens outside the
repository.

## Install from PyPI

With `uv`:

```console
uvx --from gsc-readonly-mcp gsc-mcp
```

With `pipx`:

```console
pipx install gsc-readonly-mcp
gsc-mcp
```

With `pip` in a virtual environment:

```console
python -m venv .venv
python -m pip install gsc-readonly-mcp
gsc-mcp
```

The PyPI distribution is named `gsc-readonly-mcp`; the installed command and
short project name are `gsc-mcp` / GSC MCP.

## Install from source

```console
git clone https://github.com/muryulia/google-search-console-mcp.git
cd google-search-console-mcp
python -m venv .venv
python -m pip install -e ".[dev]"
```

Run with either:

```console
gsc-mcp
python -m gsc_mcp.server
```

The process uses STDIN and STDOUT for MCP protocol messages. Diagnostics go to
STDERR and exclude query strings, page rows, tokens, credential contents, and
raw Google response bodies.

## Authentication

The server uses Google's standard ADC lookup. Common options are:

- local user ADC created with the Google Cloud CLI and the read-only Search
  Console scope;
- a service account that has been granted access to the target Search Console
  property, selected through `GOOGLE_APPLICATION_CREDENTIALS`;
- workload credentials in a supported Google Cloud environment.

Example environment variable names are provided in `.env.example`. The server
does **not** automatically load `.env`; pass variables through your shell,
secret manager, or MCP client configuration. Never commit a credential file.

On Windows or a managed network, `REQUESTS_CA_BUNDLE` or `SSL_CERT_FILE` may
point to a trusted external CA bundle. TLS verification is never disabled.
See [`docs/LOCAL_SETUP.md`](docs/LOCAL_SETUP.md) and
[`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md).

## MCP client configuration

### Codex

When `uv` is on `PATH`:

```toml
[mcp_servers.gsc_mcp]
command = "uvx"
args = ["--from", "gsc-readonly-mcp", "gsc-mcp"]
env_vars = [
  "GOOGLE_APPLICATION_CREDENTIALS",
  "SSL_CERT_FILE",
  "REQUESTS_CA_BUNDLE",
  "GRPC_DEFAULT_SSL_ROOTS_FILE_PATH",
]
enabled_tools = ["list_sites", "query_search_analytics", "inspect_url"]
startup_timeout_sec = 20
tool_timeout_sec = 120
```

### JSON-based MCP clients

Replace the credential path with an external file owned by your user account:

```json
{
  "mcpServers": {
    "gsc_mcp": {
      "command": "uvx",
      "args": ["--from", "gsc-readonly-mcp", "gsc-mcp"],
      "env": {
        "GOOGLE_APPLICATION_CREDENTIALS": "/secure/path/to/credentials.json"
      }
    }
  }
}
```

For a source checkout, point the client at the virtual environment's Python and
use `-m gsc_mcp.server`.

## Tool behavior

### `list_sites`

Input is `{}`. Output preserves Google's exact `siteUrl`; URL-prefix and
`sc-domain:` properties are never converted into one another.

### `query_search_analytics`

Required inputs:

- `site_url`
- `start_date`
- `end_date`

Optional inputs include dimensions, search type, filters, aggregation type,
manual pagination, and bounded automatic pagination. One response can contain
at most 100,000 rows. CTR remains a raw fraction and position remains Google's
average position without rounding. Dates use Pacific Time.

Search Console returns top rows within internal limits and omits anonymized
queries. A missing query is not evidence of zero demand, and results must not be
described as a complete query universe.

### `inspect_url`

Required inputs are `inspection_url` and the exact `site_url` property;
`language_code` defaults to `en-US`. The URL must be under the supplied
property. The server sends it only as data to Google's fixed URL Inspection
endpoint and never fetches the user-supplied URL.

URL Inspection describes the version in Google's index. It is not a live-page
test and never requests indexing.

## Development and verification

```console
python -m pip install -e ".[dev]"
ruff check src tests scripts
pytest
python -m build
```

The test suite verifies the exact three-tool inventory, read-only annotations,
fixed endpoint/method allowlist, bounded retries and pagination, property/URL
identity, credential-safe errors, TLS enforcement, and real STDIO discovery.

The optional live helper returns a minimized summary and does not print query or
page rows:

```console
python scripts/live_acceptance.py \
  --site-url "https://example.com/" \
  --start-date "2026-07-01" \
  --end-date "2026-07-31" \
  --inspection-url "https://example.com/"
```

A guarded OpenAI Secure MCP Tunnel workflow is documented in
[`docs/TUNNEL_SETUP.md`](docs/TUNNEL_SETUP.md). It is optional and is not needed
for ordinary local MCP clients.

## Security and privacy

GSC MCP is self-hosted. It does not provide a hosted backend, database,
telemetry service, or credential store. Data flows between the local MCP client,
this local process, and Google's fixed Search Console API endpoints.

Review [`SECURITY.md`](SECURITY.md) before deployment. Please report
vulnerabilities privately through GitHub Security Advisories rather than a
public issue.

## Support and contributing

Use [GitHub Issues](https://github.com/muryulia/google-search-console-mcp/issues)
for reproducible bugs and feature proposals. Read [`CONTRIBUTING.md`](CONTRIBUTING.md)
before submitting a change. Write-capable tools and broader OAuth scopes are
outside this project's scope.

## License

[MIT](LICENSE) © 2026 Yuliya Murtazina.

## Official references

- [Search Analytics query](https://developers.google.com/webmaster-tools/v1/searchanalytics/query)
- [Sites list](https://developers.google.com/webmaster-tools/v1/sites/list)
- [URL Inspection](https://developers.google.com/webmaster-tools/v1/urlInspection.index/inspect)
- [Search Console API limits](https://developers.google.com/webmaster-tools/limits)
- [Model Context Protocol](https://modelcontextprotocol.io/)

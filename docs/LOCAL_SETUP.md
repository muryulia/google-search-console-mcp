# Local setup and acceptance

## 1. Install

From PyPI with `uv`:

```console
uvx --from gsc-readonly-mcp gsc-mcp
```

For development from a source checkout:

```console
python -m venv .venv
python -m pip install -e ".[dev]"
```

## 2. Configure Google authentication

The server calls `google.auth.default()` with exactly this scope:

```text
https://www.googleapis.com/auth/webmasters.readonly
```

Enable the Search Console API in the relevant Google Cloud project, then
provide Application Default Credentials (ADC) that can access the target Search
Console property. See Google's official
[Search Console authorization guide](https://developers.google.com/webmaster-tools/v1/how-tos/authorizing)
and [local ADC guide](https://docs.cloud.google.com/docs/authentication/set-up-adc-local-dev-environment).

For an external ADC or service-account file:

```powershell
$env:GOOGLE_APPLICATION_CREDENTIALS = "C:\SECURE\PATH\credentials.json"
```

```bash
export GOOGLE_APPLICATION_CREDENTIALS=/secure/path/credentials.json
```

Do not put the file under the repository. The server does not load `.env`
automatically; set variables in the process environment or MCP client.

A service-account identity must be explicitly granted access to the Search
Console property. Local user ADC for non-Google-Cloud scopes can require a
custom OAuth client and explicit `--scopes`; follow the Google ADC guide rather
than broadening the scope in this project.

Use `list_sites` to verify effective access. The existence of an ADC file alone
does not prove that the required scope or property permission is present.

## 3. Optional Windows CA configuration

The server inherits the standard certificate environment. On a managed Windows
network, point it to a trusted CA bundle stored outside the repository:

```powershell
$env:SSL_CERT_FILE = "C:\SECURE\PATH\windows_ca_bundle.pem"
$env:REQUESTS_CA_BUNDLE = $env:SSL_CERT_FILE
$env:GRPC_DEFAULT_SSL_ROOTS_FILE_PATH = $env:SSL_CERT_FILE
```

The Google OAuth refresh session and Search Console API session receive the same
verified CA bundle. Never work around a trust failure with `verify=False`.

## 4. Start

```console
gsc-mcp
```

or from a source checkout:

```console
python -m gsc_mcp.server
```

The process waits for MCP messages on STDIN. It prints no banner to STDOUT.

## 5. Automated acceptance

```console
ruff check src tests scripts
pytest
python -m build
```

The suite checks the exact three-tool inventory, read-only annotations, fixed
outbound endpoint/method allowlist, filters, pagination, URL/property identity,
secret-safe errors, TLS enforcement, and real subprocess STDIO discovery.

## 6. Optional live acceptance

Use a finalized date range and a known URL under an accessible property:

```console
python scripts/live_acceptance.py \
  --site-url "https://example.com/" \
  --start-date "2026-07-01" \
  --end-date "2026-07-31" \
  --inspection-url "https://example.com/"
```

Pass requires an exact property match, real Search Analytics rows with named
fields, URL Inspection output, only the three expected tools, and no credentials
or query/page rows in the minimized report.

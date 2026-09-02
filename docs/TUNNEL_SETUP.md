# Optional Secure MCP Tunnel setup

This workflow is only for users who want to expose their local STDIO server to
a compatible OpenAI development app. Ordinary local MCP clients do not need a
tunnel. The tunnel is transport only; the server's fixed three-tool allowlist
remains the read-only enforcement boundary.

Official reference:
[OpenAI Secure MCP Tunnel](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels).

## Local names

Recommended names:

- tunnel: `Google Search Console MCP`
- local profile: `gsc-mcp`
- development app: `Google Search Console`
- transport: `Tunnel`
- app authentication: `None`

Google authentication occurs locally through the user's ADC. Create a dedicated
profile instead of reusing an unrelated tunnel profile.

## Required external values

Obtain these from your own OpenAI Platform organization and keep them out of
Git:

1. a tunnel ID from Platform tunnel settings;
2. a runtime key exposed to the process as `CONTROL_PLANE_API_KEY`;
3. the permissions required to use that tunnel.

The generated profile must contain only the reference
`env:CONTROL_PLANE_API_KEY`, never the key value.

## Windows environment

```powershell
$env:CONTROL_PLANE_API_KEY = "<runtime API key>"
$env:GOOGLE_APPLICATION_CREDENTIALS = "C:\SECURE\PATH\credentials.json"

# Optional managed-network CA bundle.
$env:SSL_CERT_FILE = "C:\SECURE\PATH\windows_ca_bundle.pem"
$env:REQUESTS_CA_BUNDLE = $env:SSL_CERT_FILE
$env:GRPC_DEFAULT_SSL_ROOTS_FILE_PATH = $env:SSL_CERT_FILE
```

## Guarded source-checkout preflight

The helper is validated against `tunnel-client 0.0.13`. Revalidate the CLI
contract before changing that pinned version.

```powershell
$tunnelClient = "C:\PATH\TO\tunnel-client.exe"
$tunnelId = "tunnel_0123456789abcdef0123456789abcdef"

.\scripts\tunnel_acceptance.ps1 `
  -TunnelId $tunnelId `
  -TunnelClientPath $tunnelClient
```

The helper:

- creates only the dedicated `gsc-mcp` profile;
- refuses to overwrite an existing profile implicitly;
- stores only the environment reference to the runtime key;
- verifies the exact MCP executable and `python -m gsc_mcp.server` target;
- binds its health endpoint to an OS-assigned loopback port;
- compares authoritative `doctor --json` checks with the requested values.

After reviewing an existing `gsc-mcp` profile, rerun with
`-UseExistingProfile`. The script initializes and validates configuration; it
does not start a background service.

## Run and inspect health

```powershell
$tunnelClient = "C:\PATH\TO\tunnel-client.exe"
$healthUrlFile = Join-Path `
  ([System.IO.Path]::GetTempPath()) `
  ("gsc-mcp-health-" + [guid]::NewGuid().ToString("N") + ".url")

& $tunnelClient run `
  --profile gsc-mcp `
  --health.url-file $healthUrlFile
```

Keep the foreground process running. In another shell:

```powershell
$healthBaseUrl = (Get-Content -LiteralPath $healthUrlFile -Raw).TrimEnd('/')
Invoke-RestMethod "$healthBaseUrl/healthz"
Invoke-RestMethod "$healthBaseUrl/readyz"
```

Expected channel state is `enabled=true`, `transport=stdio`, and
`probe_status=ok`. The listener remains loopback-only; no public inbound port is
needed.

## Development app acceptance

Create a development app using your tunnel and confirm discovery exposes
exactly:

- `list_sites`
- `query_search_analytics`
- `inspect_url`

Start with `list_sites`, then use an exact returned property identifier for
Search Analytics or URL Inspection. Do not describe Search Analytics rows as a
complete query universe.

## Rollback

Stop the foreground tunnel process, disconnect the development app, and point
the MCP command back to the last accepted release. No Search Console data
rollback is required because the server cannot mutate Search Console.

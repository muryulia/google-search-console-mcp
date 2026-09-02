# Troubleshooting

## Structured error types

| Error type | Meaning |
|---|---|
| `invalid_request` | Local validation or Google HTTP 400 |
| `authentication_failed` | Google HTTP 401 |
| `permission_denied` | Google HTTP 403 |
| `property_or_resource_not_found` | Google HTTP 404 |
| `quota_or_rate_limit` | Google HTTP 429 after bounded retries |
| `upstream_google_error` | Google 5xx after bounded retries |
| `upstream_timeout` | Connect/read timeout |
| `certificate_error` | TLS certificate validation failure |
| `blocked_outbound_request` | Method/host/path outside the read-only allowlist |

Raw Google response bodies and exception details are not returned because they
can contain sensitive material.

## ADC or 401/403

1. Confirm that the intended ADC identity is active.
2. Confirm the effective scope is
   `https://www.googleapis.com/auth/webmasters.readonly`.
3. Call `list_sites` and use the exact returned `site_url`.
4. Do not convert a URL-prefix property into `sc-domain:` or the reverse.

## TLS certificate error on Windows

1. Confirm both `SSL_CERT_FILE` and `REQUESTS_CA_BUNDLE` point to the validated
   local CA bundle.
2. Confirm the paths exist in the same shell that starts the server or tunnel.
3. Run the live acceptance helper from that shell.
4. Keep verification enabled. Do not set `verify=False`, `CERT_NONE`, or an
   unverified SSL context.

## Search Analytics returns fewer rows than expected

This is not necessarily a pagination defect. Google returns top rows within
internal limits and omits anonymized queries. Grouping/filtering by query or
page can omit additional data. Do not label the result “all queries” and do not
infer zero demand from an absent query.

## STDIO startup fails

Run from the repository root with the environment's Python:

```powershell
.\.venv\Scripts\python.exe -m gsc_mcp.server
```

Then run:

```powershell
.\.venv\Scripts\pytest.exe tests\test_stdio.py -q
```

Logs belong on STDERR. Any `print()` or banner written to STDOUT can corrupt MCP
JSON-RPC framing.

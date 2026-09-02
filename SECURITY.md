# Security policy

## Supported versions

Security fixes are provided for the latest released `0.2.x` version. Older
pre-release versions may be used for historical comparison but are not
supported.

## Reporting a vulnerability

Do not open a public issue for a suspected vulnerability or credential leak.
Use the repository's private
[GitHub Security Advisory form](https://github.com/muryulia/google-search-console-mcp/security/advisories/new).

Include:

- the affected version or commit;
- a minimal reproduction that does not contain real credentials or GSC data;
- the expected security impact;
- any suggested mitigation.

You should receive an acknowledgement within seven days. Please allow time to
validate and release a fix before public disclosure.

## Security boundary

The project intentionally exposes exactly three read-only tools:
`list_sites`, `query_search_analytics`, and `inspect_url`. It requests only
`https://www.googleapis.com/auth/webmasters.readonly` and restricts outbound
requests to fixed official Google hosts, paths, and methods.

Although Search Analytics and URL Inspection use HTTP `POST`, they are query
operations. The server contains no site, sitemap, Indexing API, arbitrary HTTP,
or other mutation capability. Contributions that add write tools or broader
OAuth scopes will not be accepted.

The server is self-hosted and does not intentionally persist credentials or
Google Search Console responses. Operators remain responsible for protecting
their local ADC files, environment, MCP client configuration, logs, and host.

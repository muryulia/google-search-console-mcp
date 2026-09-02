# Test report — v0.2.0 public-release candidate

Date: 2026-09-02
Repository: `muryulia/google-search-console-mcp`
Branch: `main`
Status: release-candidate validation passed; tag and PyPI publication pending

## Release identity

| Field | Value |
|---|---|
| Public title | Google Search Console MCP |
| Short name | GSC MCP |
| Python distribution | `gsc-readonly-mcp` |
| Import package | `gsc_mcp` |
| Console command | `gsc-mcp` |
| License | MIT |
| Copyright | Yuliya Murtazina |

The exact public title is intentionally independent from the unique PyPI
distribution identifier.

## Automated validation

| Gate | Result |
|---|---|
| Ruff | PASS |
| Pytest | PASS — 65 tests |
| Exact tool inventory | PASS — 3 tools |
| MCP resources and prompts | PASS — none |
| Read-only annotations | PASS |
| No-write endpoint/method allowlist | PASS |
| Credential-safe errors and logs | PASS |
| TLS verification and shared CA handling | PASS |
| Filters and bounded pagination | PASS |
| URL/property identity validation | PASS |
| PowerShell tunnel contract | PASS |
| GitHub YAML syntax | PASS — 3 files parsed |
| GitHub Actions candidate CI | PASS — 7/7 jobs |

The three discovered tools are `list_sites`, `query_search_analytics`, and
`inspect_url`. No write-capable tool is present.

The first private CI run exposed a Python 3.10-only test dependency issue:
`tomllib` is standard-library only from Python 3.11. The release test now uses
an explicit conditional `tomli` dependency/fallback. The repeated matrix passed
on Python 3.10, 3.11, and 3.12 on both Ubuntu and Windows; the separate package
build/smoke job also passed.

## Package build and clean-install acceptance

A clean Python 3.12.13 environment built the source distribution and wheel with
PEP 517 isolation. Both artifacts passed `twine check`. The wheel was installed
into a second, newly created virtual environment together with dependencies.

Installed-wheel smoke acceptance passed:

- distribution: `gsc-readonly-mcp`;
- installed version: `0.2.0`;
- console entry point: `gsc-mcp = gsc_mcp.server:main`;
- real STDIO initialization: PASS;
- discovered tools: exact three;
- resources: 0;
- prompts: 0.

The wheel contains only `gsc_mcp`, package metadata, the console entry point,
and the MIT license. The source distribution contains the expected public
source, documentation, tests, and release workflows, with no legacy package
path.

A first build attempt with the pre-existing local Anaconda-derived Python 3.11
failed while its nested environment imported `_ctypes`. Repeating the same
isolated build with a clean bundled Python 3.12 runtime passed. This was
classified as a host-runtime defect, not a package or test failure; no global
Python installation was changed.

## Secret and publication-boundary validation

Gitleaks `8.30.0` was downloaded from its official GitHub release into a
temporary directory and verified against the official release checksum before
execution.

| Scope | Result |
|---|---|
| Staged publishable release tree | PASS — 0 findings |
| Complete branch Git history | PASS — 0 findings |
| Real `.env` tracked | No — ignored and untracked |
| Credential/token values printed or copied | No |

The public repository is intentionally created from the reviewed release tree
with a clean history. Internal project history, tags, acceptance identifiers,
and local configuration are not part of the public repository.

## External gates still pending

- public-repository CI confirmation on `main`;
- GitHub `pypi` environment and PyPI pending Trusted Publisher;
- annotated tag and GitHub Release `v0.2.0`;
- PyPI upload and post-publication `uvx`/`pipx` verification.

No release tag, GitHub Release, or PyPI project is created by repository
preparation alone.

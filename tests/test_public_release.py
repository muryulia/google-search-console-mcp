from __future__ import annotations

import re
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

import gsc_mcp

ROOT = Path(__file__).parents[1]


def test_public_package_metadata() -> None:
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]

    assert metadata["name"] == "gsc-readonly-mcp"
    assert metadata["version"] == "0.2.0"
    assert metadata["license"] == "MIT"
    assert metadata["authors"] == [{"name": "Yuliya Murtazina"}]
    assert metadata["scripts"] == {"gsc-mcp": "gsc_mcp.server:main"}
    assert gsc_mcp.__version__ == metadata["version"]


def test_mit_license_is_present() -> None:
    license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")

    assert license_text.startswith("MIT License")
    assert "Copyright (c) 2026 Yuliya Murtazina" in license_text


def test_public_head_contains_no_legacy_private_identifiers() -> None:
    legacy_prefix = "".join(chr(codepoint) for codepoint in (106, 114, 109))
    forbidden = {
        f"{legacy_prefix}_gsc_mcp",
        f"{legacy_prefix}-gsc",
        f"{legacy_prefix}accessories.com",
        f"{legacy_prefix}-ga4",
        "propri" + "etary",
    }
    excluded_parts = {".git", ".venv", "__pycache__", ".pytest_cache", ".ruff_cache"}
    text_suffixes = {".example", ".md", ".ps1", ".py", ".toml", ".yaml", ".yml"}
    files = [
        path
        for path in ROOT.rglob("*")
        if path.is_file()
        and not excluded_parts.intersection(path.parts)
        and (path.suffix in text_suffixes or path.name in {"LICENSE", ".gitignore"})
    ]

    public_text = "\n".join(path.read_text(encoding="utf-8") for path in files).lower()
    assert all(marker not in public_text for marker in forbidden)
    tunnel_ids = set(re.findall(r"tunnel_[0-9a-f]{32}", public_text))
    assert tunnel_ids <= {"tunnel_0123456789abcdef0123456789abcdef"}

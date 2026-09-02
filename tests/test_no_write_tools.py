from __future__ import annotations

import asyncio
from pathlib import Path

from gsc_mcp import server

EXPECTED_TOOLS = {"list_sites", "query_search_analytics", "inspect_url"}
FORBIDDEN_ENDPOINT_MARKERS = {
    "sites.add",
    "sites.delete",
    "sitemaps.submit",
    "sitemaps.delete",
    "request_indexing",
    "indexing.googleapis.com",
}


def test_registered_tool_surface_is_exactly_three_read_only_tools() -> None:
    tools = asyncio.run(server.mcp.list_tools())

    assert {tool.name for tool in tools} == EXPECTED_TOOLS
    for tool in tools:
        assert tool.description is not None
        assert "read-only" in tool.description.lower()
        assert tool.annotations is not None
        assert tool.annotations.read_only_hint is True
        assert tool.annotations.destructive_hint is False
        assert tool.annotations.idempotent_hint is True


def test_source_contains_no_write_endpoint_markers() -> None:
    source_root = Path(__file__).parents[1] / "src"
    source_text = "\n".join(
        path.read_text(encoding="utf-8") for path in source_root.rglob("*.py")
    ).lower()

    for marker in FORBIDDEN_ENDPOINT_MARKERS:
        assert marker not in source_text


def test_server_exposes_no_resources_or_prompts() -> None:
    assert asyncio.run(server.mcp.list_resources()) == []
    assert asyncio.run(server.mcp.list_prompts()) == []

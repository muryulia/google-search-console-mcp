from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from mcp import Client
from mcp.client.stdio import StdioServerParameters


async def _discover_tools_over_real_stdio() -> set[str]:
    project_root = Path(__file__).parents[1]
    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "gsc_mcp.server"],
        cwd=project_root,
        env=os.environ.copy(),
    )
    async with Client(parameters, raise_exceptions=True) as client:
        result = await client.list_tools()
        return {tool.name for tool in result.tools}


def test_real_stdio_initialize_and_tool_discovery() -> None:
    discovered = asyncio.run(
        asyncio.wait_for(_discover_tools_over_real_stdio(), timeout=20.0)
    )

    assert discovered == {"list_sites", "query_search_analytics", "inspect_url"}

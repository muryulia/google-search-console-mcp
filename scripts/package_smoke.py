"""Smoke-test an installed GSC MCP wheel over real STDIO."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import tempfile
from importlib.metadata import entry_points, version

from mcp import Client
from mcp.client.stdio import StdioServerParameters

EXPECTED_TOOLS = {"list_sites", "query_search_analytics", "inspect_url"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-version", required=True)
    return parser.parse_args()


async def discover() -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="gsc-mcp-smoke-") as clean_cwd:
        parameters = StdioServerParameters(
            command=sys.executable,
            args=["-m", "gsc_mcp.server"],
            cwd=clean_cwd,
            env=os.environ.copy(),
        )
        async with Client(parameters, raise_exceptions=True) as client:
            tools = await client.list_tools()
            resources = await client.list_resources()
            prompts = await client.list_prompts()

    names = {tool.name for tool in tools.tools}
    if names != EXPECTED_TOOLS:
        raise RuntimeError(f"Unexpected tool inventory: {sorted(names)}")
    if resources.resources or prompts.prompts:
        raise RuntimeError("The installed server exposed resources or prompts.")

    return {
        "tools": sorted(names),
        "resources": 0,
        "prompts": 0,
    }


def main() -> None:
    args = parse_args()
    installed_version = version("gsc-readonly-mcp")
    if installed_version != args.expected_version:
        raise RuntimeError(
            f"Expected version {args.expected_version}, found {installed_version}."
        )

    scripts = {
        item.name: item.value
        for item in entry_points(group="console_scripts")
        if item.name == "gsc-mcp"
    }
    if scripts != {"gsc-mcp": "gsc_mcp.server:main"}:
        raise RuntimeError(f"Unexpected console entry point: {scripts}")

    report = asyncio.run(asyncio.wait_for(discover(), timeout=30.0))
    report.update(
        {
            "distribution": "gsc-readonly-mcp",
            "version": installed_version,
            "console_script": scripts["gsc-mcp"],
            "result": "PASS",
        }
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

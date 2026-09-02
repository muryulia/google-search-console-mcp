"""Minimized live ADC/TLS/STDIO acceptance for the GSC MCP server."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

from mcp import Client
from mcp.client.stdio import StdioServerParameters
from mcp.types import CallToolResult

EXPECTED_TOOLS = {"list_sites", "query_search_analytics", "inspect_url"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site-url", required=True)
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--inspection-url", required=True)
    parser.add_argument("--row-limit", type=int, default=10)
    return parser.parse_args()


def structured_result(result: CallToolResult) -> dict[str, Any]:
    payload = result.structured_content
    if result.is_error or not isinstance(payload, dict):
        raise RuntimeError("MCP tool returned an error or no structured content.")
    if "error" in payload:
        error = payload["error"]
        if isinstance(error, dict):
            error_type = error.get("error_type", "unknown_error")
            status_code = error.get("status_code")
            raise RuntimeError(f"MCP tool error: {error_type} status={status_code}")
        raise RuntimeError("MCP tool returned a structured error.")
    return payload


async def run_acceptance(args: argparse.Namespace) -> dict[str, Any]:
    project_root = Path(__file__).parents[1]
    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "gsc_mcp.server"],
        cwd=project_root,
        env=os.environ.copy(),
    )
    async with Client(parameters, raise_exceptions=True) as client:
        discovery = await client.list_tools()
        tool_names = {tool.name for tool in discovery.tools}
        if tool_names != EXPECTED_TOOLS:
            raise RuntimeError(f"Unexpected MCP tool inventory: {sorted(tool_names)}")

        sites = structured_result(await client.call_tool("list_sites", {}))
        matching_sites = [
            site
            for site in sites.get("sites", [])
            if isinstance(site, dict) and site.get("site_url") == args.site_url
        ]
        if not matching_sites:
            raise RuntimeError("Expected exact Search Console property was not returned.")

        analytics = structured_result(
            await client.call_tool(
                "query_search_analytics",
                {
                    "site_url": args.site_url,
                    "start_date": args.start_date,
                    "end_date": args.end_date,
                    "dimensions": ["query", "page"],
                    "row_limit": args.row_limit,
                },
            )
        )
        rows = analytics.get("rows")
        if not isinstance(rows, list) or not rows:
            raise RuntimeError("Search Analytics returned no rows for the acceptance fixture.")
        required_row_fields = {
            "query",
            "page",
            "clicks",
            "impressions",
            "ctr",
            "position",
        }
        if not isinstance(rows[0], dict) or not required_row_fields.issubset(rows[0]):
            raise RuntimeError("Search Analytics row did not contain the required named fields.")

        inspection = structured_result(
            await client.call_tool(
                "inspect_url",
                {
                    "inspection_url": args.inspection_url,
                    "site_url": args.site_url,
                    "language_code": "en-US",
                },
            )
        )
        warnings = inspection.get("warnings", [])
        if not any("not a live-page test" in warning for warning in warnings):
            raise RuntimeError("URL Inspection live-test limitation warning was missing.")

        analytics_warnings = analytics.get("warnings", [])
        if not any("does not guarantee all data rows" in warning for warning in analytics_warnings):
            raise RuntimeError("Search Analytics completeness warning was missing.")

        return {
            "result": "PASS",
            "tools": sorted(tool_names),
            "site_count": sites.get("count"),
            "matched_site": {
                "site_url": matching_sites[0].get("site_url"),
                "permission_level": matching_sites[0].get("permission_level"),
            },
            "analytics": {
                "row_count": analytics.get("row_count"),
                "named_fields_present": True,
                "completeness_warning_present": True,
                "date_timezone": analytics.get("date_timezone"),
            },
            "inspection": {
                "verdict": inspection.get("verdict"),
                "coverage_state": inspection.get("coverage_state"),
                "indexed_state_warning_present": True,
            },
        }


def main() -> None:
    args = parse_args()
    report = asyncio.run(asyncio.wait_for(run_acceptance(args), timeout=180.0))
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

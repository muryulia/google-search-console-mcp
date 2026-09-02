"""STDIO MCP server exposing exactly three read-only Search Console tools."""

from __future__ import annotations

import logging
import sys
from typing import Annotated, Any

from mcp.server import MCPServer
from mcp.types import ToolAnnotations
from pydantic import Field

from . import __version__
from .client import SearchConsoleClient
from .errors import GSCError
from .models import AggregationType, Dimension, SearchFilter, SearchType

SERVER_NAME = "Google Search Console MCP"
SERVER_DESCRIPTION = (
    "Read-only access to first-party Google Search Console data for SEO and "
    "content intelligence."
)
SERVER_INSTRUCTIONS = (
    "This server is strictly read-only. It exposes Search Console properties, "
    "Search Analytics, and indexed-state URL Inspection data. Never describe "
    "Search Analytics results as a complete query universe, and never interpret "
    "a missing query as zero demand."
)

READ_ONLY_ANNOTATIONS = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=True,
)

mcp = MCPServer(
    name=SERVER_NAME,
    version=__version__,
    description=SERVER_DESCRIPTION,
    instructions=SERVER_INSTRUCTIONS,
    log_level="WARNING",
)

_client: SearchConsoleClient | None = None


def _get_client() -> SearchConsoleClient:
    global _client
    if _client is None:
        _client = SearchConsoleClient()
    return _client


def _error_payload(error: GSCError) -> dict[str, Any]:
    return {"error": error.to_dict()}


@mcp.tool(
    name="list_sites",
    title="List Search Console properties",
    description=(
        "Read-only. List every Google Search Console property available to the current "
        "ADC identity, preserving each exact property identifier and permission level."
    ),
    annotations=READ_ONLY_ANNOTATIONS,
)
def list_sites() -> dict[str, Any]:
    """List accessible Search Console properties without modifying Google state."""

    try:
        return _get_client().list_sites()
    except GSCError as error:
        return _error_payload(error)


@mcp.tool(
    name="query_search_analytics",
    title="Query Search Analytics",
    description=(
        "Read-only. Query first-party Google Search Console performance data and return "
        "named dimensions with clicks, impressions, raw CTR fraction, and Search Console "
        "average position. Results are top rows, not a complete query universe."
    ),
    annotations=READ_ONLY_ANNOTATIONS,
)
def query_search_analytics(
    site_url: Annotated[str, Field(description="Exact Search Console property identifier.")],
    start_date: Annotated[str, Field(description="Inclusive PT start date in YYYY-MM-DD.")],
    end_date: Annotated[str, Field(description="Inclusive PT end date in YYYY-MM-DD.")],
    dimensions: list[Dimension] | None = None,
    search_type: SearchType = "web",
    filters: list[SearchFilter] | None = None,
    aggregation_type: AggregationType = "auto",
    row_limit: Annotated[int, Field(ge=1, le=25_000)] = 1000,
    start_row: Annotated[int, Field(ge=0)] = 0,
    fetch_all: bool = False,
    max_rows: Annotated[int, Field(ge=1, le=100_000)] = 100_000,
) -> dict[str, Any]:
    """Run one Search Analytics page without modifying Search Console."""

    try:
        return _get_client().query_search_analytics(
            site_url=site_url,
            start_date=start_date,
            end_date=end_date,
            dimensions=dimensions,
            search_type=search_type,
            filters=filters,
            aggregation_type=aggregation_type,
            row_limit=row_limit,
            start_row=start_row,
            fetch_all=fetch_all,
            max_rows=max_rows,
        )
    except GSCError as error:
        return _error_payload(error)


@mcp.tool(
    name="inspect_url",
    title="Inspect indexed URL state",
    description=(
        "Read-only. Return Google URL Inspection information for the version currently "
        "in Google's index. This is not a live URL test and never requests indexing."
    ),
    annotations=READ_ONLY_ANNOTATIONS,
)
def inspect_url(
    inspection_url: Annotated[
        str,
        Field(description="Fully-qualified URL under the supplied property.", max_length=4096),
    ],
    site_url: Annotated[str, Field(description="Exact Search Console property identifier.")],
    language_code: Annotated[
        str,
        Field(description="BCP-47 response language.", min_length=2, max_length=35),
    ] = "en-US",
) -> dict[str, Any]:
    """Inspect Google's indexed state without performing a live-page test."""

    try:
        return _get_client().inspect_url(
            inspection_url=inspection_url,
            site_url=site_url,
            language_code=language_code,
        )
    except GSCError as error:
        return _error_payload(error)


def main() -> None:
    """Start the server over STDIO without contaminating protocol stdout."""

    logging.basicConfig(
        level=logging.WARNING,
        stream=sys.stderr,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()

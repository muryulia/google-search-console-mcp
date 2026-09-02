"""Public input vocabulary for the MCP tools."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Dimension = Literal[
    "query",
    "page",
    "country",
    "device",
    "date",
    "hour",
    "searchAppearance",
]
FilterDimension = Literal["query", "page", "country", "device", "searchAppearance"]
FilterOperator = Literal[
    "contains",
    "equals",
    "notContains",
    "notEquals",
    "includingRegex",
    "excludingRegex",
]
SearchType = Literal["web", "image", "video", "news", "discover", "googleNews"]
AggregationType = Literal["auto", "byPage", "byProperty"]


class SearchFilter(BaseModel):
    """One official Search Console dimension filter."""

    model_config = ConfigDict(extra="forbid")

    dimension: FilterDimension
    operator: FilterOperator
    expression: str = Field(min_length=1, max_length=4096)

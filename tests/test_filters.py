from __future__ import annotations

import pytest
from pydantic import ValidationError

from gsc_mcp.client import SearchConsoleClient
from gsc_mcp.models import SearchFilter
from tests.test_list_sites import FakeResponse, FakeSession


def test_filters_map_to_single_official_and_group() -> None:
    session = FakeSession([FakeResponse(200, {"rows": []})])
    client = SearchConsoleClient(session=session)
    filter_ = SearchFilter(dimension="query", operator="contains", expression="brass")

    client.query_search_analytics(
        site_url="https://example.com/",
        start_date="2026-08-01",
        end_date="2026-08-31",
        filters=[filter_],
    )

    assert session.calls[0]["json"]["dimensionFilterGroups"] == [
        {
            "groupType": "and",
            "filters": [
                {
                    "dimension": "query",
                    "operator": "contains",
                    "expression": "brass",
                }
            ],
        }
    ]


def test_filter_rejects_unknown_operator() -> None:
    with pytest.raises(ValidationError):
        SearchFilter.model_validate(
            {
                "dimension": "query",
                "operator": "startsWith",
                "expression": "brass",
            }
        )


def test_filter_rejects_nonfilter_dimension_and_large_expression() -> None:
    with pytest.raises(ValidationError):
        SearchFilter.model_validate(
            {
                "dimension": "date",
                "operator": "equals",
                "expression": "2026-08-01",
            }
        )
    with pytest.raises(ValidationError):
        SearchFilter(
            dimension="query",
            operator="contains",
            expression="x" * 4097,
        )

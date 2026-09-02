from __future__ import annotations

import pytest

from gsc_mcp.client import (
    SEARCH_ANALYTICS_PRIVACY_WARNING,
    SEARCH_ANALYTICS_WARNING,
    SearchConsoleClient,
)
from gsc_mcp.errors import GSCError
from tests.test_list_sites import FakeResponse, FakeSession


def test_query_search_analytics_normalizes_named_dimensions() -> None:
    session = FakeSession(
        [
            FakeResponse(
                200,
                {
                    "rows": [
                        {
                            "keys": [
                                "aged brass cup pulls",
                                "https://example.com/products/example",
                            ],
                            "clicks": 3.0,
                            "impressions": 41.0,
                            "ctr": 0.0731707317,
                            "position": 8.4,
                        }
                    ],
                    "responseAggregationType": "auto",
                },
            )
        ]
    )
    client = SearchConsoleClient(session=session)

    result = client.query_search_analytics(
        site_url="https://example.com/",
        start_date="2026-08-01",
        end_date="2026-08-31",
        dimensions=["query", "page"],
        row_limit=10,
    )

    assert result["rows"] == [
        {
            "query": "aged brass cup pulls",
            "page": "https://example.com/products/example",
            "clicks": 3.0,
            "impressions": 41.0,
            "ctr": 0.0731707317,
            "position": 8.4,
        }
    ]
    assert result["date_timezone"] == "PT"
    assert result["warnings"] == [
        SEARCH_ANALYTICS_WARNING,
        SEARCH_ANALYTICS_PRIVACY_WARNING,
    ]
    assert result["response_aggregation_type"] == "auto"

    call = session.calls[0]
    assert call["method"] == "POST"
    assert call["url"] == (
        "https://www.googleapis.com/webmasters/v3/sites/"
        "https%3A%2F%2Fexample.com%2F/searchAnalytics/query"
    )
    assert call["json"] == {
        "startDate": "2026-08-01",
        "endDate": "2026-08-31",
        "type": "web",
        "aggregationType": "auto",
        "rowLimit": 10,
        "startRow": 0,
        "dimensions": ["query", "page"],
    }
    assert "searchType" not in call["json"]


def test_query_preserves_domain_property_without_rewrite() -> None:
    session = FakeSession([FakeResponse(200, {"rows": []})])
    client = SearchConsoleClient(session=session)

    result = client.query_search_analytics(
        site_url="sc-domain:example.com",
        start_date="2026-08-01",
        end_date="2026-08-02",
    )

    assert result["site_url"] == "sc-domain:example.com"
    assert "sc-domain%3Aexample.com" in session.calls[0]["url"]
    assert "https%3A" not in session.calls[0]["url"]


@pytest.mark.parametrize(
    ("start_date", "end_date"),
    [
        ("2026/08/01", "2026-08-31"),
        ("2026-8-01", "2026-08-31"),
        ("2026-09-01", "2026-08-31"),
    ],
)
def test_query_rejects_invalid_date_range(start_date: str, end_date: str) -> None:
    client = SearchConsoleClient(session=FakeSession([]))

    with pytest.raises(GSCError) as caught:
        client.query_search_analytics(
            site_url="https://example.com/",
            start_date=start_date,
            end_date=end_date,
        )

    assert caught.value.error_type == "invalid_request"


def test_query_rejects_search_appearance_with_other_dimensions() -> None:
    client = SearchConsoleClient(session=FakeSession([]))

    with pytest.raises(GSCError, match="searchAppearance must be queried alone"):
        client.query_search_analytics(
            site_url="https://example.com/",
            start_date="2026-08-01",
            end_date="2026-08-31",
            dimensions=["searchAppearance", "query"],
        )


def test_query_rejects_mismatched_positional_keys() -> None:
    session = FakeSession(
        [
            FakeResponse(
                200,
                {
                    "rows": [
                        {
                            "keys": ["query only"],
                            "clicks": 1,
                            "impressions": 2,
                            "ctr": 0.5,
                            "position": 1.0,
                        }
                    ]
                },
            )
        ]
    )
    client = SearchConsoleClient(session=session)

    with pytest.raises(GSCError, match="keys did not match"):
        client.query_search_analytics(
            site_url="https://example.com/",
            start_date="2026-08-01",
            end_date="2026-08-31",
            dimensions=["query", "page"],
        )


def test_query_validation_happens_before_network() -> None:
    session = FakeSession([])
    client = SearchConsoleClient(session=session)

    with pytest.raises(GSCError):
        client.query_search_analytics(
            site_url="https://example.com.evil.test/",
            start_date="2026-08-31",
            end_date="2026-08-01",
        )

    assert session.calls == []

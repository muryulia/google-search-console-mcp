from __future__ import annotations

from typing import Any

import pytest

import gsc_mcp.client as client_module
from gsc_mcp.client import (
    FETCH_ALL_TRUNCATED_WARNING,
    SEARCH_ANALYTICS_WARNING,
    SearchConsoleClient,
)
from gsc_mcp.errors import GSCError
from tests.test_list_sites import FakeResponse, FakeSession


def row(query: str) -> dict[str, Any]:
    return {
        "keys": [query],
        "clicks": 1,
        "impressions": 2,
        "ctr": 0.5,
        "position": 3.25,
    }


def test_fetch_all_paginates_preserves_order_and_does_not_deduplicate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(client_module, "FETCH_ALL_PAGE_SIZE", 2)
    session = FakeSession(
        [
            FakeResponse(200, {"rows": [row("same"), row("same")]}),
            FakeResponse(200, {"rows": [row("last")]}),
        ]
    )
    client = SearchConsoleClient(session=session)

    result = client.query_search_analytics(
        site_url="https://example.com/",
        start_date="2026-08-01",
        end_date="2026-08-31",
        dimensions=["query"],
        fetch_all=True,
    )

    assert [item["query"] for item in result["rows"]] == ["same", "same", "last"]
    assert [call["json"]["startRow"] for call in session.calls] == [0, 2]
    assert [call["json"]["rowLimit"] for call in session.calls] == [2, 2]
    assert result["row_count"] == 3
    assert result["truncated"] is False
    assert SEARCH_ANALYTICS_WARNING in result["warnings"]


def test_fetch_all_enforces_ceiling_and_marks_truncation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(client_module, "FETCH_ALL_PAGE_SIZE", 2)
    session = FakeSession(
        [
            FakeResponse(200, {"rows": [row("a"), row("b")]}),
            FakeResponse(200, {"rows": [row("c"), row("d")]}),
        ]
    )
    client = SearchConsoleClient(session=session)

    result = client.query_search_analytics(
        site_url="https://example.com/",
        start_date="2026-08-01",
        end_date="2026-08-31",
        dimensions=["query"],
        fetch_all=True,
        max_rows=3,
    )

    assert [item["query"] for item in result["rows"]] == ["a", "b", "c"]
    assert result["truncated"] is True
    assert FETCH_ALL_TRUNCATED_WARNING in result["warnings"]


@pytest.mark.parametrize(("row_limit", "start_row"), [(0, 0), (25_001, 0), (10, -1)])
def test_manual_pagination_rejects_invalid_bounds(row_limit: int, start_row: int) -> None:
    client = SearchConsoleClient(session=FakeSession([]))

    with pytest.raises(GSCError):
        client.query_search_analytics(
            site_url="https://example.com/",
            start_date="2026-08-01",
            end_date="2026-08-31",
            row_limit=row_limit,
            start_row=start_row,
        )

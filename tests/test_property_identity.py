from __future__ import annotations

import pytest

from gsc_mcp.client import SearchConsoleClient
from gsc_mcp.errors import GSCError
from tests.test_list_sites import FakeResponse, FakeSession


@pytest.mark.parametrize(
    "site_url",
    [
        "https://example.com/",
        "http://example.com/catalog/",
        "sc-domain:example.com",
    ],
)
def test_query_preserves_property_identifier_byte_for_byte(site_url: str) -> None:
    session = FakeSession([FakeResponse(200, {"rows": []})])
    client = SearchConsoleClient(session=session)

    result = client.query_search_analytics(
        site_url=site_url,
        start_date="2026-08-01",
        end_date="2026-08-02",
    )

    assert result["site_url"] == site_url


def test_url_prefix_property_is_not_satisfied_by_domain_property() -> None:
    session = FakeSession([])
    client = SearchConsoleClient(session=session)

    with pytest.raises(GSCError, match="not under the exact supplied"):
        client.inspect_url(
            inspection_url="https://shop.example.com/page",
            site_url="https://example.com/",
        )

    assert session.calls == []


def test_path_scoped_property_requires_exact_path_prefix() -> None:
    session = FakeSession([])
    client = SearchConsoleClient(session=session)

    with pytest.raises(GSCError):
        client.inspect_url(
            inspection_url="https://example.com/shopping/item",
            site_url="https://example.com/shop/",
        )

    assert session.calls == []


@pytest.mark.parametrize(
    "site_url",
    [
        "https://example.com",
        "sc-domain:https://example.com/",
        "https://example.com:invalid/",
        "https://user:password@example.com/",
        "https://example.com/\r\nInjected: value",
    ],
)
def test_invalid_property_identifiers_are_rejected(site_url: str) -> None:
    client = SearchConsoleClient(session=FakeSession([]))

    with pytest.raises(GSCError):
        client.query_search_analytics(
            site_url=site_url,
            start_date="2026-08-01",
            end_date="2026-08-02",
        )

from __future__ import annotations

import pytest

from gsc_mcp.client import (
    URL_INSPECTION_ENDPOINT,
    URL_INSPECTION_WARNING,
    SearchConsoleClient,
)
from gsc_mcp.errors import GSCError
from tests.test_list_sites import FakeResponse, FakeSession


def test_inspect_url_normalizes_indexed_state_and_never_fetches_target() -> None:
    inspected_url = "https://example.com/blogs/guides/example"
    session = FakeSession(
        [
            FakeResponse(
                200,
                {
                    "inspectionResult": {
                        "inspectionResultLink": "https://search.google.com/test/result",
                        "indexStatusResult": {
                            "verdict": "PASS",
                            "coverageState": "Submitted and indexed",
                            "robotsTxtState": "ALLOWED",
                            "indexingState": "INDEXING_ALLOWED",
                            "lastCrawlTime": "2026-08-30T12:00:00Z",
                            "pageFetchState": "SUCCESSFUL",
                            "googleCanonical": inspected_url,
                            "userCanonical": inspected_url,
                            "sitemap": ["https://example.com/sitemap.xml"],
                            "referringUrls": ["https://example.com/blogs/guides"],
                        },
                        "mobileUsabilityResult": {"verdict": "PASS", "issues": []},
                        "richResultsResult": {
                            "verdict": "PASS",
                            "detectedItems": [{"richResultType": "Breadcrumbs"}],
                        },
                    }
                },
            )
        ]
    )
    client = SearchConsoleClient(session=session)

    result = client.inspect_url(
        inspection_url=inspected_url,
        site_url="https://example.com/",
    )

    assert result["warnings"] == [URL_INSPECTION_WARNING]
    assert result["verdict"] == "PASS"
    assert result["coverage_state"] == "Submitted and indexed"
    assert result["last_crawl_time"] == "2026-08-30T12:00:00Z"
    assert result["mobile_usability"] == {"verdict": "PASS", "issues": []}
    assert result["rich_results"]["detected_items"] == [
        {"rich_result_type": "Breadcrumbs"}
    ]
    assert session.calls == [
        {
            "method": "POST",
            "url": URL_INSPECTION_ENDPOINT,
            "json": {
                "inspectionUrl": inspected_url,
                "siteUrl": "https://example.com/",
                "languageCode": "en-US",
            },
            "timeout": (15.0, 60.0),
        }
    ]
    assert all(call["url"] != inspected_url for call in session.calls)


@pytest.mark.parametrize(
    "inspection_url",
    [
        "https://example.com.evil.test/page",
        "https://example.com@evil.test/page",
        "http://127.0.0.1/private",
        "https://example.com/\r\nX-Test: injected",
    ],
)
def test_inspect_url_rejects_boundary_and_injection_attacks(inspection_url: str) -> None:
    session = FakeSession([])
    client = SearchConsoleClient(session=session)

    with pytest.raises(GSCError):
        client.inspect_url(
            inspection_url=inspection_url,
            site_url="https://example.com/",
        )

    assert session.calls == []


def test_inspect_url_accepts_subdomain_under_domain_property() -> None:
    session = FakeSession(
        [
            FakeResponse(
                200,
                {
                    "inspectionResult": {
                        "indexStatusResult": {},
                    }
                },
            )
        ]
    )
    client = SearchConsoleClient(session=session)

    result = client.inspect_url(
        inspection_url="https://shop.example.com/page",
        site_url="sc-domain:example.com",
    )

    assert result["site_url"] == "sc-domain:example.com"
    assert result["unavailable_sections"] == ["mobile_usability", "rich_results"]


def test_inspect_url_reports_missing_sections_as_unavailable() -> None:
    session = FakeSession([FakeResponse(200, {"inspectionResult": {}})])
    client = SearchConsoleClient(session=session)

    result = client.inspect_url(
        inspection_url="https://example.com/page",
        site_url="https://example.com/",
    )

    assert result["unavailable_sections"] == [
        "index_status",
        "mobile_usability",
        "rich_results",
    ]

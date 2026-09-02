from __future__ import annotations

import asyncio
from typing import Any

import pytest

from gsc_mcp import auth, server
from gsc_mcp.client import SITES_ENDPOINT, SearchConsoleClient
from gsc_mcp.errors import GSCError


class FakeResponse:
    def __init__(self, status_code: int, payload: Any) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> Any:
        return self._payload


class FakeSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []
        self.closed = False

    def request(self, method: str, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append({"method": method, "url": url, **kwargs})
        return self.responses.pop(0)

    def close(self) -> None:
        self.closed = True


def test_list_sites_normalizes_exact_property_identity() -> None:
    session = FakeSession(
        [
            FakeResponse(
                200,
                {
                    "siteEntry": [
                        {
                            "siteUrl": "https://example.com/",
                            "permissionLevel": "siteFullUser",
                        },
                        {
                            "siteUrl": "sc-domain:example.com",
                            "permissionLevel": "siteRestrictedUser",
                        },
                    ]
                },
            )
        ]
    )
    client = SearchConsoleClient(session=session)

    result = client.list_sites()

    assert result == {
        "sites": [
            {
                "site_url": "https://example.com/",
                "permission_level": "siteFullUser",
            },
            {
                "site_url": "sc-domain:example.com",
                "permission_level": "siteRestrictedUser",
            },
        ],
        "count": 2,
    }
    assert session.calls == [
        {
            "method": "GET",
            "url": SITES_ENDPOINT,
            "json": None,
            "timeout": (15.0, 60.0),
        }
    ]


def test_list_sites_retries_only_transient_status() -> None:
    session = FakeSession(
        [
            FakeResponse(429, {"error": {"message": "quota"}}),
            FakeResponse(200, {"siteEntry": []}),
        ]
    )
    sleeps: list[float] = []
    client = SearchConsoleClient(session=session, sleep=sleeps.append)

    assert client.list_sites() == {"sites": [], "count": 0}
    assert len(session.calls) == 2
    assert sleeps == [0.5]


def test_list_sites_does_not_retry_permission_error() -> None:
    session = FakeSession([FakeResponse(403, {"error": {"message": "secret"}})])
    client = SearchConsoleClient(session=session, sleep=lambda _seconds: None)

    with pytest.raises(GSCError) as caught:
        client.list_sites()

    assert caught.value.to_dict() == {
        "error_type": "permission_denied",
        "message": "Google Search Console API returned HTTP 403.",
        "status_code": 403,
    }
    assert len(session.calls) == 1


def test_auth_requests_only_readonly_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    sentinel_credentials = object()
    captured: dict[str, Any] = {}

    def fake_default(*, scopes: list[str]) -> tuple[object, str]:
        captured["scopes"] = scopes
        return sentinel_credentials, "project"

    monkeypatch.setattr(auth.google.auth, "default", fake_default)

    credentials, project_id = auth.load_credentials()

    assert credentials is sentinel_credentials
    assert project_id == "project"
    assert captured["scopes"] == [auth.READ_ONLY_SCOPE]


def test_list_sites_tool_is_registered_as_read_only() -> None:
    tools = asyncio.run(server.mcp.list_tools())
    tool = next(tool for tool in tools if tool.name == "list_sites")

    assert tool.description is not None
    assert "Read-only" in tool.description
    assert tool.annotations is not None
    assert tool.annotations.read_only_hint is True
    assert tool.annotations.destructive_hint is False
    assert tool.annotations.idempotent_hint is True

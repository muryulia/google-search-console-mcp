"""Structured, secret-safe errors returned by the Search Console client."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class GSCError(Exception):
    """A normalized failure that is safe to expose to an MCP consumer."""

    error_type: str
    message: str
    status_code: int | None = None
    site_url: str | None = None

    def __str__(self) -> str:
        return self.message

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "error_type": self.error_type,
            "message": self.message,
        }
        if self.status_code is not None:
            result["status_code"] = self.status_code
        if self.site_url is not None:
            result["site_url"] = self.site_url
        return result


def http_error(status_code: int, site_url: str | None = None) -> GSCError:
    """Map an HTTP status without exposing an upstream response body."""

    error_types = {
        400: "invalid_request",
        401: "authentication_failed",
        403: "permission_denied",
        404: "property_or_resource_not_found",
        429: "quota_or_rate_limit",
    }
    error_type = error_types.get(status_code)
    if error_type is None:
        error_type = "upstream_google_error" if status_code >= 500 else "http_error"
    return GSCError(
        error_type=error_type,
        status_code=status_code,
        message=f"Google Search Console API returned HTTP {status_code}.",
        site_url=site_url,
    )

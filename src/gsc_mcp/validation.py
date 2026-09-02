"""Validation that preserves exact Search Console property identity."""

from __future__ import annotations

import re
from datetime import date
from ipaddress import ip_address
from urllib.parse import urlsplit

from .errors import GSCError
from .models import Dimension, SearchFilter

_CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f\x7f]")
_DOMAIN_NAME = re.compile(
    r"(?=.{1,253}\Z)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+"
    r"[A-Za-z](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\Z"
)
_LANGUAGE_CODE = re.compile(r"[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*\Z")


def invalid_input(message: str, site_url: str | None = None) -> GSCError:
    return GSCError("invalid_request", message, status_code=400, site_url=site_url)


def validate_site_url(site_url: str) -> str:
    """Validate syntax without converting URL-prefix and Domain properties."""

    if not site_url or len(site_url) > 2048 or _CONTROL_CHARACTERS.search(site_url):
        raise invalid_input("site_url is empty, too long, or contains control characters.")

    if site_url.startswith("sc-domain:"):
        domain = site_url.removeprefix("sc-domain:")
        if not _DOMAIN_NAME.fullmatch(domain):
            raise invalid_input("sc-domain site_url must contain one valid domain name.", site_url)
        return site_url

    parsed = urlsplit(site_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise invalid_input("URL-prefix site_url must be an absolute HTTP(S) URL.", site_url)
    try:
        parsed_port = parsed.port
    except ValueError as exc:
        raise invalid_input("site_url contains an invalid port.", site_url) from exc
    if parsed_port == 0:
        raise invalid_input("site_url contains an invalid port.", site_url)
    if parsed.username is not None or parsed.password is not None:
        raise invalid_input("site_url must not contain user information.", site_url)
    if parsed.query or parsed.fragment:
        raise invalid_input("site_url must not contain a query string or fragment.", site_url)
    if not site_url.endswith("/"):
        raise invalid_input("URL-prefix site_url must preserve its trailing slash.", site_url)
    return site_url


def validate_date_range(start_date: str, end_date: str) -> tuple[str, str]:
    try:
        parsed_start = date.fromisoformat(start_date)
        parsed_end = date.fromisoformat(end_date)
    except ValueError as exc:
        raise invalid_input("start_date and end_date must use YYYY-MM-DD.") from exc
    if parsed_start.isoformat() != start_date or parsed_end.isoformat() != end_date:
        raise invalid_input("start_date and end_date must use canonical YYYY-MM-DD.")
    if parsed_start > parsed_end:
        raise invalid_input("start_date must be on or before end_date.")
    return start_date, end_date


def validate_dimensions(dimensions: list[Dimension] | None) -> list[Dimension]:
    normalized = list(dimensions or [])
    if len(normalized) > 7:
        raise invalid_input("No more than seven dimensions are allowed.")
    if len(set(normalized)) != len(normalized):
        raise invalid_input("dimensions must not contain duplicates.")
    if "searchAppearance" in normalized and len(normalized) > 1:
        raise invalid_input(
            "searchAppearance must be queried alone and then used as a filter in a follow-up query."
        )
    return normalized


def validate_pagination(row_limit: int, start_row: int) -> tuple[int, int]:
    if isinstance(row_limit, bool) or not 1 <= row_limit <= 25_000:
        raise invalid_input("row_limit must be between 1 and 25000.")
    if isinstance(start_row, bool) or start_row < 0:
        raise invalid_input("start_row must be zero or greater.")
    return row_limit, start_row


def validate_filters(filters: list[SearchFilter] | None) -> list[SearchFilter]:
    normalized = list(filters or [])
    if len(normalized) > 20:
        raise invalid_input("No more than 20 filters are allowed.")
    return normalized


def validate_fetch_all(fetch_all: bool, max_rows: int) -> tuple[bool, int]:
    if not isinstance(fetch_all, bool):
        raise invalid_input("fetch_all must be a boolean.")
    if isinstance(max_rows, bool) or not 1 <= max_rows <= 100_000:
        raise invalid_input("max_rows must be between 1 and 100000.")
    return fetch_all, max_rows


def validate_inspection_request(
    inspection_url: str,
    site_url: str,
    language_code: str,
) -> tuple[str, str, str]:
    """Validate URL Inspection inputs without fetching the supplied URL."""

    exact_site_url = validate_site_url(site_url)
    if (
        not inspection_url
        or len(inspection_url) > 4096
        or _CONTROL_CHARACTERS.search(inspection_url)
    ):
        raise invalid_input(
            "inspection_url is empty, too long, or contains control characters.",
            exact_site_url,
        )
    parsed = urlsplit(inspection_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise invalid_input(
            "inspection_url must be a fully-qualified HTTP(S) URL.",
            exact_site_url,
        )
    if parsed.username is not None or parsed.password is not None:
        raise invalid_input("inspection_url must not contain user information.", exact_site_url)
    if parsed.fragment:
        raise invalid_input("inspection_url must not contain a fragment.", exact_site_url)
    try:
        inspection_port = parsed.port
    except ValueError as exc:
        raise invalid_input("inspection_url contains an invalid port.", exact_site_url) from exc
    try:
        address = ip_address(parsed.hostname)
    except ValueError:
        address = None
    if address is not None and (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_reserved
        or address.is_unspecified
    ):
        raise invalid_input(
            "inspection_url must not target a private or special-use IP address.",
            exact_site_url,
        )

    if exact_site_url.startswith("sc-domain:"):
        domain = exact_site_url.removeprefix("sc-domain:").lower()
        hostname = parsed.hostname.lower()
        belongs = hostname == domain or hostname.endswith(f".{domain}")
    else:
        property_url = urlsplit(exact_site_url)
        try:
            property_port = property_url.port
        except ValueError as exc:
            raise invalid_input("site_url contains an invalid port.", exact_site_url) from exc
        belongs = (
            parsed.scheme.lower() == property_url.scheme.lower()
            and parsed.hostname.lower() == property_url.hostname.lower()
            and _effective_port(parsed.scheme, inspection_port)
            == _effective_port(property_url.scheme, property_port)
            and parsed.path.startswith(property_url.path)
        )
    if not belongs:
        raise invalid_input(
            "inspection_url is not under the exact supplied Search Console property.",
            exact_site_url,
        )

    if len(language_code) > 35 or not _LANGUAGE_CODE.fullmatch(language_code):
        raise invalid_input("language_code must be a valid BCP-47 style tag.", exact_site_url)
    return inspection_url, exact_site_url, language_code


def _effective_port(scheme: str, explicit_port: int | None) -> int | None:
    if explicit_port is not None:
        return explicit_port
    return {"http": 80, "https": 443}.get(scheme.lower())

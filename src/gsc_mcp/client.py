"""Fixed-host, read-only HTTP client for Google Search Console."""

from __future__ import annotations

import logging
import re
import time
from collections.abc import Callable
from typing import Any, Protocol
from urllib.parse import quote, urlsplit

from google.auth.exceptions import TransportError as GoogleAuthTransportError
from requests import Response
from requests.exceptions import RequestException, SSLError, Timeout

from .auth import close_session, create_authorized_session
from .errors import GSCError, http_error
from .models import AggregationType, Dimension, SearchFilter, SearchType
from .validation import (
    validate_date_range,
    validate_dimensions,
    validate_fetch_all,
    validate_filters,
    validate_inspection_request,
    validate_pagination,
    validate_site_url,
)

logger = logging.getLogger(__name__)

SITES_ENDPOINT = "https://www.googleapis.com/webmasters/v3/sites"
URL_INSPECTION_ENDPOINT = "https://searchconsole.googleapis.com/v1/urlInspection/index:inspect"
SEARCH_ANALYTICS_WARNING = (
    "Search Console API does not guarantee all data rows; it returns top rows within "
    "internal limits."
)
SEARCH_ANALYTICS_PRIVACY_WARNING = (
    "Anonymized queries are omitted; absence of a query does not establish zero demand."
)
FETCH_ALL_TRUNCATED_WARNING = "Local fetch_all safety ceiling reached; rows were truncated."
FETCH_ALL_PAGE_SIZE = 25_000
URL_INSPECTION_WARNING = (
    "URL Inspection API reports Google-indexed state, not a live-page test."
)
TRANSIENT_STATUS_CODES = frozenset({429, 500, 502, 503, 504})
DEFAULT_TIMEOUT = (15.0, 60.0)
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_BACKOFF_SECONDS = 0.5


class HTTPSession(Protocol):
    """Minimal requests-compatible surface used by the client."""

    def request(self, method: str, url: str, **kwargs: Any) -> Response: ...

    def close(self) -> None: ...


class SearchConsoleClient:
    """Read-only client with an outbound endpoint allowlist and bounded retries."""

    def __init__(
        self,
        session: HTTPSession | None = None,
        *,
        timeout: tuple[float, float] = DEFAULT_TIMEOUT,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        backoff_seconds: float = DEFAULT_BACKOFF_SECONDS,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if max_attempts < 1 or max_attempts > 5:
            raise ValueError("max_attempts must be between 1 and 5")
        self._session = session or create_authorized_session()
        self._timeout = timeout
        self._max_attempts = max_attempts
        self._backoff_seconds = max(0.0, backoff_seconds)
        self._sleep = sleep

    def close(self) -> None:
        close_session(self._session)

    def __enter__(self) -> SearchConsoleClient:
        return self

    def __exit__(self, *_exc_info: object) -> None:
        self.close()

    def list_sites(self) -> dict[str, Any]:
        """Return the exact property identifiers and permission levels from Google."""

        payload, status_code, duration_ms = self._request_json("GET", SITES_ENDPOINT)
        entries = payload.get("siteEntry", [])
        if not isinstance(entries, list):
            raise GSCError(
                "invalid_upstream_response",
                "Google Search Console sites response did not contain a valid siteEntry list.",
            )

        sites: list[dict[str, str]] = []
        for entry in entries:
            if not isinstance(entry, dict):
                raise GSCError(
                    "invalid_upstream_response",
                    "Google Search Console returned an invalid site entry.",
                )
            site_url = entry.get("siteUrl")
            permission_level = entry.get("permissionLevel")
            if not isinstance(site_url, str) or not isinstance(permission_level, str):
                raise GSCError(
                    "invalid_upstream_response",
                    "Google Search Console returned an incomplete site entry.",
                )
            sites.append(
                {
                    "site_url": site_url,
                    "permission_level": permission_level,
                }
            )

        logger.info(
            "tool=list_sites status=%s duration_ms=%.1f site_count=%s",
            status_code,
            duration_ms,
            len(sites),
        )
        return {"sites": sites, "count": len(sites)}

    def query_search_analytics(
        self,
        *,
        site_url: str,
        start_date: str,
        end_date: str,
        dimensions: list[Dimension] | None = None,
        search_type: SearchType = "web",
        filters: list[SearchFilter] | None = None,
        aggregation_type: AggregationType = "auto",
        row_limit: int = 1000,
        start_row: int = 0,
        fetch_all: bool = False,
        max_rows: int = 100_000,
    ) -> dict[str, Any]:
        """Run Search Analytics and optionally fetch pages to a bounded local ceiling."""

        exact_site_url = validate_site_url(site_url)
        validate_date_range(start_date, end_date)
        normalized_dimensions = validate_dimensions(dimensions)
        normalized_filters = validate_filters(filters)
        validate_pagination(row_limit, start_row)
        validate_fetch_all(fetch_all, max_rows)

        endpoint = f"{SITES_ENDPOINT}/{encode_site_url(exact_site_url)}/searchAnalytics/query"
        page_size = FETCH_ALL_PAGE_SIZE if fetch_all else row_limit
        current_start_row = start_row
        rows: list[dict[str, Any]] = []
        status_code = 0
        duration_ms = 0.0
        truncated = False
        response_aggregation: str | None = None

        while True:
            body = self._search_analytics_body(
                start_date=start_date,
                end_date=end_date,
                dimensions=normalized_dimensions,
                search_type=search_type,
                filters=normalized_filters,
                aggregation_type=aggregation_type,
                row_limit=page_size,
                start_row=current_start_row,
            )
            payload, status_code, page_duration_ms = self._request_json(
                "POST",
                endpoint,
                json_body=body,
                site_url=exact_site_url,
            )
            duration_ms += page_duration_ms
            page_rows = self._normalize_search_analytics_rows(payload, normalized_dimensions)
            if isinstance(payload.get("responseAggregationType"), str):
                response_aggregation = payload["responseAggregationType"]

            if not fetch_all:
                rows = page_rows
                break

            remaining = max_rows - len(rows)
            if len(page_rows) > remaining:
                rows.extend(page_rows[:remaining])
                truncated = True
                break
            rows.extend(page_rows)
            if len(page_rows) < page_size:
                break
            if len(rows) >= max_rows:
                truncated = True
                break
            current_start_row += page_size

        warnings = [
            SEARCH_ANALYTICS_WARNING,
            SEARCH_ANALYTICS_PRIVACY_WARNING,
        ]
        if truncated:
            warnings.append(FETCH_ALL_TRUNCATED_WARNING)
        result: dict[str, Any] = {
            "site_url": exact_site_url,
            "start_date": start_date,
            "end_date": end_date,
            "date_timezone": "PT",
            "dimensions": normalized_dimensions,
            "search_type": search_type,
            "rows": rows,
            "row_count": len(rows),
            "start_row": start_row,
            "row_limit": page_size,
            "fetch_all": fetch_all,
            "max_rows": max_rows,
            "truncated": truncated,
            "warnings": warnings,
        }
        if response_aggregation is not None:
            result["response_aggregation_type"] = response_aggregation

        logger.info(
            "tool=query_search_analytics status=%s duration_ms=%.1f row_count=%s "
            "site_url=%s date_range=%s..%s",
            status_code,
            duration_ms,
            len(rows),
            exact_site_url,
            start_date,
            end_date,
        )
        return result

    def inspect_url(
        self,
        *,
        inspection_url: str,
        site_url: str,
        language_code: str = "en-US",
    ) -> dict[str, Any]:
        """Return Google's indexed-state inspection without requesting a live test."""

        exact_inspection_url, exact_site_url, language_code = validate_inspection_request(
            inspection_url,
            site_url,
            language_code,
        )
        payload, status_code, duration_ms = self._request_json(
            "POST",
            URL_INSPECTION_ENDPOINT,
            json_body={
                "inspectionUrl": exact_inspection_url,
                "siteUrl": exact_site_url,
                "languageCode": language_code,
            },
            site_url=exact_site_url,
        )
        raw_result = payload.get("inspectionResult")
        if not isinstance(raw_result, dict):
            raise GSCError(
                "invalid_upstream_response",
                "Google URL Inspection response did not contain inspectionResult.",
                status_code=status_code,
                site_url=exact_site_url,
            )

        result: dict[str, Any] = {
            "inspection_url": exact_inspection_url,
            "site_url": exact_site_url,
            "language_code": language_code,
            "warnings": [URL_INSPECTION_WARNING],
        }
        result_link = raw_result.get("inspectionResultLink")
        if isinstance(result_link, str):
            result["inspection_result_link"] = result_link

        unavailable_sections: list[str] = []
        index_status = raw_result.get("indexStatusResult")
        if isinstance(index_status, dict):
            field_map = {
                "verdict": "verdict",
                "coverageState": "coverage_state",
                "robotsTxtState": "robots_txt_state",
                "indexingState": "indexing_state",
                "lastCrawlTime": "last_crawl_time",
                "pageFetchState": "page_fetch_state",
                "googleCanonical": "google_canonical",
                "userCanonical": "user_canonical",
                "sitemap": "sitemap",
                "referringUrls": "referring_urls",
            }
            for source_name, output_name in field_map.items():
                if source_name in index_status:
                    result[output_name] = index_status[source_name]
        else:
            unavailable_sections.append("index_status")

        mobile_usability = raw_result.get("mobileUsabilityResult")
        if isinstance(mobile_usability, dict):
            result["mobile_usability"] = self._snake_case_tree(mobile_usability)
        else:
            unavailable_sections.append("mobile_usability")

        rich_results = raw_result.get("richResultsResult")
        if isinstance(rich_results, dict):
            result["rich_results"] = self._snake_case_tree(rich_results)
        else:
            unavailable_sections.append("rich_results")

        if unavailable_sections:
            result["unavailable_sections"] = unavailable_sections

        logger.info(
            "tool=inspect_url status=%s duration_ms=%.1f site_url=%s",
            status_code,
            duration_ms,
            exact_site_url,
        )
        return result

    @staticmethod
    def _search_analytics_body(
        *,
        start_date: str,
        end_date: str,
        dimensions: list[Dimension],
        search_type: SearchType,
        filters: list[SearchFilter],
        aggregation_type: AggregationType,
        row_limit: int,
        start_row: int,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "startDate": start_date,
            "endDate": end_date,
            "type": search_type,
            "aggregationType": aggregation_type,
            "rowLimit": row_limit,
            "startRow": start_row,
        }
        if dimensions:
            body["dimensions"] = dimensions
        if filters:
            body["dimensionFilterGroups"] = [
                {
                    "groupType": "and",
                    "filters": [filter_.model_dump() for filter_ in filters],
                }
            ]
        return body

    def _request_json(
        self,
        method: str,
        url: str,
        *,
        json_body: dict[str, Any] | None = None,
        site_url: str | None = None,
    ) -> tuple[dict[str, Any], int, float]:
        self._assert_allowed_request(method, url)
        started = time.monotonic()
        response: Response | None = None

        for attempt in range(1, self._max_attempts + 1):
            try:
                response = self._session.request(
                    method,
                    url,
                    json=json_body,
                    timeout=self._timeout,
                )
            except SSLError as exc:
                raise GSCError(
                    "certificate_error",
                    "TLS certificate validation failed while contacting Google.",
                    site_url=site_url,
                ) from exc
            except GoogleAuthTransportError as exc:
                if self._exception_chain_contains_ssl_error(exc):
                    raise GSCError(
                        "certificate_error",
                        "TLS certificate validation failed while refreshing Google credentials.",
                        site_url=site_url,
                    ) from exc
                raise GSCError(
                    "upstream_network_error",
                    "Google credential refresh failed due to a network error.",
                    site_url=site_url,
                ) from exc
            except Timeout as exc:
                raise GSCError(
                    "upstream_timeout",
                    "Google Search Console API request timed out.",
                    site_url=site_url,
                ) from exc
            except RequestException as exc:
                raise GSCError(
                    "upstream_network_error",
                    "A network error occurred while contacting Google Search Console.",
                    site_url=site_url,
                ) from exc

            if response.status_code not in TRANSIENT_STATUS_CODES:
                break
            if attempt < self._max_attempts:
                self._sleep(min(self._backoff_seconds * (2 ** (attempt - 1)), 4.0))

        if response is None:
            raise GSCError("upstream_network_error", "No response was received from Google.")
        if response.status_code >= 400:
            raise http_error(response.status_code, site_url)

        try:
            payload = response.json()
        except ValueError as exc:
            raise GSCError(
                "invalid_upstream_response",
                "Google Search Console API returned a non-JSON response.",
                status_code=response.status_code,
                site_url=site_url,
            ) from exc
        if not isinstance(payload, dict):
            raise GSCError(
                "invalid_upstream_response",
                "Google Search Console API returned an invalid JSON object.",
                status_code=response.status_code,
                site_url=site_url,
            )

        duration_ms = (time.monotonic() - started) * 1000
        return payload, response.status_code, duration_ms

    @staticmethod
    def _assert_allowed_request(method: str, url: str) -> None:
        parsed = urlsplit(url)
        normalized_method = method.upper()
        sites_allowed = (
            normalized_method == "GET"
            and parsed.scheme == "https"
            and parsed.netloc == "www.googleapis.com"
            and parsed.path == "/webmasters/v3/sites"
            and not parsed.query
            and not parsed.fragment
        )
        analytics_prefix = "/webmasters/v3/sites/"
        analytics_suffix = "/searchAnalytics/query"
        analytics_segment = ""
        if parsed.path.startswith(analytics_prefix) and parsed.path.endswith(analytics_suffix):
            analytics_segment = parsed.path[len(analytics_prefix) : -len(analytics_suffix)]
        analytics_allowed = (
            normalized_method == "POST"
            and parsed.scheme == "https"
            and parsed.netloc == "www.googleapis.com"
            and bool(analytics_segment)
            and "/" not in analytics_segment
            and not parsed.query
            and not parsed.fragment
        )
        inspection_allowed = (
            normalized_method == "POST"
            and parsed.scheme == "https"
            and parsed.netloc == "searchconsole.googleapis.com"
            and parsed.path == "/v1/urlInspection/index:inspect"
            and not parsed.query
            and not parsed.fragment
        )
        if not (sites_allowed or analytics_allowed or inspection_allowed):
            raise GSCError(
                "blocked_outbound_request",
                "The requested HTTP method or endpoint is not on the read-only allowlist.",
            )

    @staticmethod
    def _normalize_search_analytics_rows(
        payload: dict[str, Any],
        dimensions: list[Dimension],
    ) -> list[dict[str, Any]]:
        raw_rows = payload.get("rows", [])
        if not isinstance(raw_rows, list):
            raise GSCError(
                "invalid_upstream_response",
                "Google Search Console returned an invalid Search Analytics rows value.",
            )

        normalized_rows: list[dict[str, Any]] = []
        for raw_row in raw_rows:
            if not isinstance(raw_row, dict):
                raise GSCError(
                    "invalid_upstream_response",
                    "Google Search Console returned an invalid Search Analytics row.",
                )
            keys = raw_row.get("keys", [])
            if not isinstance(keys, list) or len(keys) != len(dimensions):
                raise GSCError(
                    "invalid_upstream_response",
                    "Search Analytics keys did not match the requested dimensions.",
                )

            row: dict[str, Any] = dict(zip(dimensions, keys, strict=True))
            for metric in ("clicks", "impressions", "ctr", "position"):
                value = raw_row.get(metric)
                if not isinstance(value, int | float) or isinstance(value, bool):
                    raise GSCError(
                        "invalid_upstream_response",
                        f"Search Analytics row did not contain a numeric {metric} value.",
                    )
                row[metric] = value
            normalized_rows.append(row)
        return normalized_rows

    @classmethod
    def _snake_case_tree(cls, value: Any) -> Any:
        if isinstance(value, dict):
            return {
                re.sub(r"(?<!^)(?=[A-Z])", "_", str(key)).lower(): cls._snake_case_tree(item)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [cls._snake_case_tree(item) for item in value]
        return value

    @staticmethod
    def _exception_chain_contains_ssl_error(error: BaseException) -> bool:
        current: BaseException | None = error
        seen: set[int] = set()
        while current is not None and id(current) not in seen:
            if isinstance(current, SSLError):
                return True
            seen.add(id(current))
            current = current.__cause__ or current.__context__
        return False


def encode_site_url(site_url: str) -> str:
    """Encode a Search Console property as one opaque path segment."""

    return quote(site_url, safe="")

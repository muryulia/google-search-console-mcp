"""Application Default Credentials for the read-only Search Console scope."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import google.auth
import requests
from google.auth.credentials import Credentials
from google.auth.exceptions import DefaultCredentialsError
from google.auth.transport.requests import AuthorizedSession, Request

from .errors import GSCError

READ_ONLY_SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"
SCOPES = (READ_ONLY_SCOPE,)


def load_credentials() -> tuple[Credentials, str | None]:
    """Load ADC with the only OAuth scope permitted by this server."""

    try:
        credentials, project_id = google.auth.default(scopes=list(SCOPES))
    except DefaultCredentialsError as exc:
        raise GSCError(
            "authentication_failed",
            "Application Default Credentials are unavailable or invalid.",
        ) from exc
    return credentials, project_id


def create_authorized_session() -> AuthorizedSession:
    """Create API and token-refresh sessions with the same verified CA bundle."""

    credentials, _project_id = load_credentials()
    ca_bundle = _configured_ca_bundle()

    refresh_session = requests.Session()
    api_session = AuthorizedSession(
        credentials,
        auth_request=Request(session=refresh_session),
        refresh_timeout=60.0,
    )
    if ca_bundle is not None:
        refresh_session.verify = ca_bundle
        api_session.verify = ca_bundle

    api_session._gsc_refresh_session = refresh_session
    return api_session


def close_session(session: Any) -> None:
    """Close a requests-compatible session when it supports explicit cleanup."""

    refresh_session = getattr(session, "_gsc_refresh_session", None)
    refresh_close = getattr(refresh_session, "close", None)
    if callable(refresh_close):
        refresh_close()
    close = getattr(session, "close", None)
    if callable(close):
        close()


def _configured_ca_bundle() -> str | None:
    """Resolve, but never modify, the inherited CA environment."""

    configured = os.environ.get("REQUESTS_CA_BUNDLE") or os.environ.get("SSL_CERT_FILE")
    if not configured:
        return None
    path = Path(configured)
    if not path.is_file():
        raise GSCError(
            "certificate_error",
            "The configured CA bundle path does not reference a readable file.",
        )
    return str(path)

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


SHEETS_DRIVE_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]
GMAIL_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"


def build_google_services(
    credentials_path: str | None,
    oauth_client_secret_path: str | None = None,
    oauth_token_path: str = "secrets/google-oauth-token.json",
    scopes: list[str] | None = None,
    services: tuple[tuple[str, str], ...] = (("sheets", "v4"), ("drive", "v3")),
) -> tuple[Any, ...]:
    from googleapiclient.discovery import build

    credentials = get_google_credentials(
        credentials_path=credentials_path,
        oauth_client_secret_path=oauth_client_secret_path,
        oauth_token_path=oauth_token_path,
        scopes=scopes or SHEETS_DRIVE_SCOPES,
    )
    return tuple(build(service, version, credentials=credentials) for service, version in services)


def get_google_credentials(
    credentials_path: str | None,
    oauth_client_secret_path: str | None = None,
    oauth_token_path: str = "secrets/google-oauth-token.json",
    scopes: list[str] | None = None,
) -> Any:
    from google.auth.transport.requests import Request
    from google.oauth2 import service_account
    from google.oauth2.credentials import Credentials

    resolved_scopes = scopes or SHEETS_DRIVE_SCOPES
    service_account_path = usable_path(credentials_path)
    oauth_secret_path = usable_path(oauth_client_secret_path) or discover_oauth_client_secret()
    token_path = os.path.expanduser(oauth_token_path)
    credentials = None

    if service_account_path:
        return service_account.Credentials.from_service_account_file(service_account_path, scopes=resolved_scopes)

    if os.path.exists(token_path) and _token_file_has_required_scopes(token_path, resolved_scopes):
        try:
            credentials = Credentials.from_authorized_user_file(token_path, scopes=resolved_scopes)
        except ValueError:
            credentials = None
    if credentials and not _has_required_scopes(credentials, resolved_scopes):
        credentials = None
    if credentials and not credentials.valid and credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
        Path(token_path).parent.mkdir(parents=True, exist_ok=True)
        Path(token_path).write_text(credentials.to_json(), encoding="utf-8")
    if credentials and credentials.valid:
        return credentials

    if oauth_secret_path:
        from google_auth_oauthlib.flow import InstalledAppFlow

        flow = InstalledAppFlow.from_client_secrets_file(oauth_secret_path, resolved_scopes)
        oauth_port = int(os.getenv("GOOGLE_OAUTH_PORT", "8080"))
        credentials = flow.run_local_server(port=oauth_port, access_type="offline", prompt="consent")
        if credentials:
            Path(token_path).parent.mkdir(parents=True, exist_ok=True)
            Path(token_path).write_text(credentials.to_json(), encoding="utf-8")
            return credentials

    raise RuntimeError(
        "Set GOOGLE_APPLICATION_CREDENTIALS for a service account or "
        "GOOGLE_OAUTH_CLIENT_SECRET for local OAuth access."
    )


def profile_oauth_scopes(include_gmail: bool = False) -> list[str]:
    scopes = list(SHEETS_DRIVE_SCOPES)
    if include_gmail:
        scopes.append(GMAIL_SEND_SCOPE)
    return scopes


def usable_path(path: str | None) -> str | None:
    if not path:
        return None
    expanded = os.path.expanduser(path.strip())
    if not expanded or expanded.startswith("/absolute/path/to/"):
        return None
    return expanded if os.path.exists(expanded) else None


def discover_oauth_client_secret() -> str | None:
    for candidate in os.listdir("."):
        if candidate.startswith("client_secret") and candidate.endswith(".json") and os.path.exists(candidate):
            return candidate
    return None


def _has_required_scopes(credentials: Any, scopes: list[str]) -> bool:
    if hasattr(credentials, "has_scopes"):
        return bool(credentials.has_scopes(scopes))
    return True


def _token_file_has_required_scopes(token_path: str, scopes: list[str]) -> bool:
    try:
        data = json.loads(Path(token_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    token_scopes = data.get("scopes")
    if isinstance(token_scopes, str):
        granted_scopes = set(token_scopes.split())
    elif isinstance(token_scopes, list):
        granted_scopes = {str(scope) for scope in token_scopes}
    else:
        return False
    return set(scopes).issubset(granted_scopes)

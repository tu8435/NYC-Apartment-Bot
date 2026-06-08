from __future__ import annotations

import os
from pathlib import Path

from apartment_search.google_auth import get_google_credentials, profile_oauth_scopes
from apartment_search.preferences import profile_dir_for_name


def oauth_token_path_for_profile(profile_name: str) -> Path:
    return profile_dir_for_name(profile_name) / "google-oauth-token.json"


def authenticate_profile(profile_name: str, include_gmail: bool = True) -> Path:
    token_path = oauth_token_path_for_profile(profile_name)
    get_google_credentials(
        credentials_path=None,
        oauth_client_secret_path=os.getenv("GOOGLE_OAUTH_CLIENT_SECRET"),
        oauth_token_path=str(token_path),
        scopes=profile_oauth_scopes(include_gmail=include_gmail),
    )
    return token_path

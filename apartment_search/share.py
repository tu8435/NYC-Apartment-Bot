from __future__ import annotations

import base64
import json
import os
from email.message import EmailMessage
from pathlib import Path
from typing import Any

from apartment_search.google_auth import build_google_services, profile_oauth_scopes
from apartment_search.preferences import profile_dir_for_name
from apartment_search.profile_auth import oauth_token_path_for_profile


def share_profile(profile_name: str, target_email: str) -> dict[str, Any]:
    profile_dir = profile_dir_for_name(profile_name)
    preferences_path = profile_dir / "preferences.json"
    workspace_path = profile_dir / "workspace.json"
    if not preferences_path.exists():
        raise FileNotFoundError(f"Missing profile preferences: {preferences_path}")
    if not workspace_path.exists():
        raise FileNotFoundError(f"Missing profile workspace: {workspace_path}")

    message = EmailMessage()
    message["To"] = target_email
    message["Subject"] = f"RentRank profile: {profile_name}"
    message.set_content(
        "Attached are the shareable RentRank profile files.\n\n"
        "Save them as preferences.json and workspace.json under your local "
        f"secrets/config/profiles/{profile_name}/ folder, then run:\n\n"
        f"rentrank-nyc auth --profile-name {profile_name}\n"
    )
    _attach_json(message, "preferences.json", _load_json(preferences_path))
    _attach_json(message, "workspace.json", _load_json(workspace_path))

    (gmail_service,) = build_google_services(
        credentials_path=None,
        oauth_client_secret_path=os.getenv("GOOGLE_OAUTH_CLIENT_SECRET"),
        oauth_token_path=str(oauth_token_path_for_profile(profile_name)),
        scopes=profile_oauth_scopes(include_gmail=True),
        services=(("gmail", "v1"),),
    )
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
    sent = gmail_service.users().messages().send(userId="me", body={"raw": raw}).execute()
    return {"profile_name": profile_name, "target_email": target_email, "gmail_message_id": sent.get("id")}


def _attach_json(message: EmailMessage, filename: str, payload: dict[str, Any]) -> None:
    content = json.dumps(payload, indent=2) + "\n"
    message.add_attachment(content, subtype="json", filename=filename)


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return data



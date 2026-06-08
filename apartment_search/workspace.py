from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PRIVATE_WORKSPACE_PATH = Path("secrets/config/workspace.json")
EXAMPLE_WORKSPACE_PATH = Path(__file__).resolve().parent.parent / "config" / "workspace.example.json"


@dataclass(slots=True)
class WorkspaceConfig:
    google_sheets_spreadsheet_id: str = ""
    google_drive_folder_id: str = ""
    google_drive_folder_link: str = ""
    google_sheets_title: str = "RentRank NYC Candidates"
    google_oauth_token_path: str = "secrets/google-oauth-token.json"
    create_spreadsheet_if_missing: bool = False


def load_workspace_config(path: str | Path | None = None, apply_env_overrides: bool = True) -> WorkspaceConfig:
    base = _load_workspace_data(EXAMPLE_WORKSPACE_PATH)
    if path is None:
        path = _default_workspace_path()
    data = _load_workspace_data(path)
    merged = base | data
    if apply_env_overrides:
        merged = _with_env_overrides(merged)
    return WorkspaceConfig(
        google_sheets_spreadsheet_id=str(merged.get("google_sheets_spreadsheet_id", "")).strip(),
        google_drive_folder_id=str(merged.get("google_drive_folder_id", "")).strip(),
        google_drive_folder_link=str(merged.get("google_drive_folder_link", "")).strip(),
        google_sheets_title=str(merged.get("google_sheets_title", "RentRank NYC Candidates")).strip()
        or "RentRank NYC Candidates",
        google_oauth_token_path=str(merged.get("google_oauth_token_path", "secrets/google-oauth-token.json")).strip()
        or "secrets/google-oauth-token.json",
        create_spreadsheet_if_missing=_as_bool(merged.get("create_spreadsheet_if_missing", False)),
    )


def write_default_workspace(path: str | Path) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(_load_workspace_data(EXAMPLE_WORKSPACE_PATH), indent=2) + "\n", encoding="utf-8")


def _default_workspace_path() -> Path:
    configured = (os.getenv("RENTRANK_WORKSPACE_PATH") or "").strip()
    if configured:
        return Path(configured)
    if PRIVATE_WORKSPACE_PATH.exists():
        return PRIVATE_WORKSPACE_PATH
    return EXAMPLE_WORKSPACE_PATH


def _load_workspace_data(path: str | Path) -> dict[str, Any]:
    workspace_path = Path(path)
    with workspace_path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ValueError(f"Workspace config at {workspace_path} must be a JSON object.")
    return data


def _with_env_overrides(data: dict[str, Any]) -> dict[str, Any]:
    merged = dict(data)
    env_map = {
        "google_sheets_spreadsheet_id": "GOOGLE_SHEETS_SPREADSHEET_ID",
        "google_drive_folder_id": "GOOGLE_DRIVE_FOLDER_ID",
        "google_sheets_title": "GOOGLE_SHEETS_TITLE",
        "google_oauth_token_path": "GOOGLE_OAUTH_TOKEN",
        "create_spreadsheet_if_missing": "RENTRANK_CREATE_SPREADSHEET_IF_MISSING",
    }
    for key, env_name in env_map.items():
        if value := (os.getenv(env_name) or "").strip():
            merged[key] = _env_bool(value) if key == "create_spreadsheet_if_missing" else value
    return merged


def _env_bool(value: str) -> bool:
    return value.lower() in {"1", "true", "yes", "y", "on"}


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return _env_bool(value)
    return bool(value)

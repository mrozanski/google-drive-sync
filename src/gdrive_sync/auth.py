"""OAuth2 authentication for Google Drive/Sheets using global config."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from gdrive_sync.global_config import GlobalConfig, GlobalConfigError

SCOPES: Iterable[str] = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/spreadsheets.readonly",
]


class AuthenticationError(Exception):
    """Raised when authentication fails."""


def authenticate(global_config: GlobalConfig) -> Credentials:
    """Authenticate with Google APIs using global credentials directory."""
    if not global_config.has_credentials():
        raise GlobalConfigError(
            "Credentials missing. Run `gdrive-sync setup` and provide your OAuth client credentials JSON."
        )

    token_path = global_config.token_path
    credentials_path: Path = global_config.credentials_path
    creds: Credentials | None = None

    if token_path.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
        except Exception:
            creds = None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as exc:
                raise AuthenticationError(f"Failed to refresh token: {exc}")
        else:
            try:
                flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), SCOPES)
                creds = flow.run_local_server(port=0)
            except Exception as exc:
                raise AuthenticationError(f"Failed to authenticate with provided credentials: {exc}")

        try:
            token_path.write_text(creds.to_json())
        except Exception as exc:
            raise AuthenticationError(f"Could not persist token: {exc}")

    return creds


def get_drive_service(global_config: GlobalConfig):
    creds = authenticate(global_config)
    try:
        return build("drive", "v3", credentials=creds)
    except Exception as exc:
        raise AuthenticationError(f"Failed to build Drive service: {exc}")


def get_sheets_service(global_config: GlobalConfig):
    creds = authenticate(global_config)
    try:
        return build("sheets", "v4", credentials=creds)
    except Exception as exc:
        raise AuthenticationError(f"Failed to build Sheets service: {exc}")

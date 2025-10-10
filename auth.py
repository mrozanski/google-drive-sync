"""Google Drive OAuth2 authentication."""

import os
import pickle
from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Scopes define what access we're requesting
# https://www.googleapis.com/auth/drive.readonly - read-only access to Drive
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']


class AuthenticationError(Exception):
    """Raised when authentication fails."""
    pass


def authenticate(credentials_file: Path, token_file: str = "token.json") -> Credentials:
    """Authenticate with Google Drive using OAuth2.

    Args:
        credentials_file: Path to the OAuth2 credentials JSON file
        token_file: Path to store the token (default: token.json)

    Returns:
        Credentials: Valid Google OAuth2 credentials

    Raises:
        AuthenticationError: If authentication fails
    """
    creds = None
    token_path = Path(token_file)

    # Load existing token if available
    if token_path.exists():
        try:
            with open(token_path, 'rb') as token:
                creds = pickle.load(token)
        except Exception as e:
            print(f"Warning: Could not load existing token: {e}")
            creds = None

    # If no valid credentials, authenticate
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                print("Refreshing access token...")
                creds.refresh(Request())
            except Exception as e:
                raise AuthenticationError(
                    f"Failed to refresh token: {e}\n"
                    "You may need to re-authenticate. Delete token.json and try again."
                )
        else:
            # Run OAuth2 flow
            try:
                print("Starting OAuth2 authentication...")
                print("A browser window will open for you to authorize the application.")
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(credentials_file),
                    SCOPES,
                    # Request offline access to get refresh token
                )
                # Use run_local_server for better user experience
                creds = flow.run_local_server(port=0)
                print("Authentication successful!")
            except Exception as e:
                raise AuthenticationError(
                    f"Failed to authenticate: {e}\n"
                    "Please check your credentials file and try again."
                )

        # Save the credentials for future runs
        try:
            with open(token_path, 'wb') as token:
                pickle.dump(creds, token)
            print(f"Token saved to {token_file}")
        except Exception as e:
            print(f"Warning: Could not save token: {e}")

    return creds


def get_drive_service(credentials_file: Path, token_file: str = "token.json"):
    """Get authenticated Google Drive service.

    Args:
        credentials_file: Path to the OAuth2 credentials JSON file
        token_file: Path to store the token (default: token.json)

    Returns:
        Resource: Google Drive API service instance

    Raises:
        AuthenticationError: If authentication fails
    """
    creds = authenticate(credentials_file, token_file)
    try:
        service = build('drive', 'v3', credentials=creds)
        return service
    except Exception as e:
        raise AuthenticationError(f"Failed to build Drive service: {e}")

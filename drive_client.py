"""Google Drive API client wrapper."""

import io
import time
from typing import List, Dict, Any, Optional
from googleapiclient.http import MediaIoBaseDownload
from googleapiclient.errors import HttpError


class DriveClientError(Exception):
    """Raised when Drive API operations fail."""
    pass


class DriveClient:
    """Wrapper for Google Drive API operations."""

    # Google Workspace MIME types
    MIME_TYPES = {
        'document': 'application/vnd.google-apps.document',
        'spreadsheet': 'application/vnd.google-apps.spreadsheet',
        'folder': 'application/vnd.google-apps.folder',
    }

    # Export formats
    EXPORT_FORMATS = {
        'document': 'text/markdown',
        'spreadsheet': 'text/csv',
    }

    def __init__(self, service, sheets_service=None):
        """Initialize Drive client with authenticated service.

        Args:
            service: Authenticated Google Drive API service
            sheets_service: Authenticated Google Sheets API service (optional)
        """
        self.service = service
        self.sheets_service = sheets_service

    def list_files(self, folder_id: str, page_size: int = 100) -> List[Dict[str, Any]]:
        """List all files in a folder (non-recursive).

        Args:
            folder_id: Google Drive folder ID
            page_size: Number of results per page (default: 100)

        Returns:
            List of file metadata dictionaries

        Raises:
            DriveClientError: If API call fails
        """
        try:
            results = []
            page_token = None

            while True:
                response = self._execute_with_retry(
                    lambda: self.service.files().list(
                        q=f"'{folder_id}' in parents and trashed=false",
                        pageSize=page_size,
                        pageToken=page_token,
                        fields="nextPageToken, files(id, name, mimeType, modifiedTime, size)",
                    ).execute()
                )

                files = response.get('files', [])
                results.extend(files)

                page_token = response.get('nextPageToken')
                if not page_token:
                    break

            return results

        except HttpError as e:
            raise DriveClientError(f"Failed to list files in folder {folder_id}: {e}")

    def get_folder_hierarchy(self, folder_id: str) -> Dict[str, Any]:
        """Recursively get all files and folders in a folder hierarchy.

        Args:
            folder_id: Google Drive folder ID to start from

        Returns:
            Dictionary with folder structure and all files

        Raises:
            DriveClientError: If API call fails
        """
        try:
            files = self.list_files(folder_id)
            result = {
                'files': [],
                'folders': []
            }

            for file in files:
                if file['mimeType'] == self.MIME_TYPES['folder']:
                    # Recursively process subfolders
                    subfolder_data = self.get_folder_hierarchy(file['id'])
                    result['folders'].append({
                        'id': file['id'],
                        'name': file['name'],
                        'contents': subfolder_data
                    })
                else:
                    result['files'].append(file)

            return result

        except Exception as e:
            raise DriveClientError(f"Failed to get folder hierarchy: {e}")

    def export_google_doc(self, file_id: str) -> bytes:
        """Export a Google Doc as Markdown.

        Args:
            file_id: Google Drive file ID

        Returns:
            File content as bytes

        Raises:
            DriveClientError: If export fails
        """
        try:
            request = self.service.files().export_media(
                fileId=file_id,
                mimeType=self.EXPORT_FORMATS['document']
            )
            content = io.BytesIO()
            downloader = MediaIoBaseDownload(content, request)

            done = False
            while not done:
                status, done = downloader.next_chunk()

            return content.getvalue()

        except HttpError as e:
            raise DriveClientError(f"Failed to export Google Doc {file_id}: {e}")

    def export_google_sheet(self, file_id: str, sheet_name: Optional[str] = None) -> bytes:
        """Export a Google Sheet (or specific sheet) as CSV.

        Args:
            file_id: Google Drive file ID
            sheet_name: Specific sheet name to export (optional)

        Returns:
            File content as bytes

        Raises:
            DriveClientError: If export fails
        """
        try:
            # Build export URL with optional sheet parameter
            mime_type = self.EXPORT_FORMATS['spreadsheet']

            if sheet_name:
                # Export specific sheet using gid parameter
                # Note: We'll need to get the sheet gid from the spreadsheet metadata
                request = self.service.files().export_media(
                    fileId=file_id,
                    mimeType=mime_type
                )
            else:
                request = self.service.files().export_media(
                    fileId=file_id,
                    mimeType=mime_type
                )

            content = io.BytesIO()
            downloader = MediaIoBaseDownload(content, request)

            done = False
            while not done:
                status, done = downloader.next_chunk()

            return content.getvalue()

        except HttpError as e:
            raise DriveClientError(f"Failed to export Google Sheet {file_id}: {e}")

    def export_sheet_tab(self, file_id: str, sheet_id: int) -> bytes:
        """Export a specific sheet tab as CSV.

        Args:
            file_id: Google Drive file ID
            sheet_id: Sheet ID (gid) to export

        Returns:
            File content as bytes

        Raises:
            DriveClientError: If export fails
        """
        try:
            # Use Drive API export with gid parameter
            # Note: This uses a direct HTTP request with the gid parameter
            import requests
            from google.auth.transport.requests import AuthorizedSession

            # Get credentials from the service
            authed_session = AuthorizedSession(self.service._http.credentials)

            # Build export URL with gid
            url = f"https://docs.google.com/spreadsheets/d/{file_id}/export?format=csv&gid={sheet_id}"

            response = authed_session.get(url)
            response.raise_for_status()

            return response.content

        except Exception as e:
            raise DriveClientError(f"Failed to export sheet tab {sheet_id} from {file_id}: {e}")

    def get_sheet_tabs(self, file_id: str) -> List[Dict[str, Any]]:
        """Get all sheet tabs/names from a Google Spreadsheet.

        Args:
            file_id: Google Drive file ID

        Returns:
            List of sheet information (title, sheetId, index)

        Raises:
            DriveClientError: If API call fails or Sheets API not available
        """
        if not self.sheets_service:
            # Fallback: return single sheet if Sheets API not available
            return [{'title': 'Sheet1', 'sheetId': 0, 'index': 0}]

        try:
            # Get spreadsheet metadata using Sheets API
            spreadsheet = self._execute_with_retry(
                lambda: self.sheets_service.spreadsheets().get(
                    spreadsheetId=file_id,
                    fields='sheets(properties(sheetId,title,index))'
                ).execute()
            )

            sheets = []
            for sheet in spreadsheet.get('sheets', []):
                props = sheet.get('properties', {})
                sheets.append({
                    'title': props.get('title', 'Sheet1'),
                    'sheetId': props.get('sheetId', 0),
                    'index': props.get('index', 0)
                })

            return sheets if sheets else [{'title': 'Sheet1', 'sheetId': 0, 'index': 0}]

        except Exception as e:
            # If Sheets API fails, fall back to single sheet
            print(f"     Warning: Could not get sheet tabs, using single export: {e}")
            return [{'title': 'Sheet1', 'sheetId': 0, 'index': 0}]

    def download_file(self, file_id: str) -> bytes:
        """Download a regular (non-Google Workspace) file.

        Args:
            file_id: Google Drive file ID

        Returns:
            File content as bytes

        Raises:
            DriveClientError: If download fails
        """
        try:
            request = self.service.files().get_media(fileId=file_id)
            content = io.BytesIO()
            downloader = MediaIoBaseDownload(content, request)

            done = False
            while not done:
                status, done = downloader.next_chunk()

            return content.getvalue()

        except HttpError as e:
            raise DriveClientError(f"Failed to download file {file_id}: {e}")

    def is_google_doc(self, mime_type: str) -> bool:
        """Check if file is a Google Doc."""
        return mime_type == self.MIME_TYPES['document']

    def is_google_sheet(self, mime_type: str) -> bool:
        """Check if file is a Google Sheet."""
        return mime_type == self.MIME_TYPES['spreadsheet']

    def is_folder(self, mime_type: str) -> bool:
        """Check if file is a folder."""
        return mime_type == self.MIME_TYPES['folder']

    def is_supported_file(self, mime_type: str) -> bool:
        """Check if file type is supported for sync.

        Supports Google Docs and Sheets (for conversion).
        Folders are handled separately.

        Args:
            mime_type: File MIME type

        Returns:
            True if file should be synced (Docs and Sheets only)
        """
        return self.is_google_doc(mime_type) or self.is_google_sheet(mime_type)

    def _execute_with_retry(self, func, max_retries: int = 3, initial_delay: float = 1.0):
        """Execute a function with exponential backoff retry.

        Args:
            func: Function to execute
            max_retries: Maximum number of retries
            initial_delay: Initial delay in seconds

        Returns:
            Function result

        Raises:
            Exception: If all retries fail
        """
        delay = initial_delay
        last_error = None

        for attempt in range(max_retries):
            try:
                return func()
            except HttpError as e:
                last_error = e
                # Check if it's a rate limit error (429) or server error (5xx)
                if e.resp.status in [429, 500, 503]:
                    if attempt < max_retries - 1:
                        print(f"Rate limit/server error, retrying in {delay}s...")
                        time.sleep(delay)
                        delay *= 2  # Exponential backoff
                        continue
                # For other errors, raise immediately
                raise

        # If we get here, all retries failed
        raise last_error

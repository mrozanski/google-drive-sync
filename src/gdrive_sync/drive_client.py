"""Google Drive API client wrapper with search and upload helpers."""
from __future__ import annotations

import io
import time
from typing import Any, Dict, List, Optional

from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload


class DriveClientError(Exception):
    """Raised when Drive API operations fail."""


class DriveClient:
    MIME_TYPES = {
        "document": "application/vnd.google-apps.document",
        "spreadsheet": "application/vnd.google-apps.spreadsheet",
        "folder": "application/vnd.google-apps.folder",
    }

    EXPORT_FORMATS = {
        "document": "text/markdown",
        "spreadsheet": "text/csv",
    }

    def __init__(self, service, sheets_service=None):
        self.service = service
        self.sheets_service = sheets_service

    # ---------- listing & search ----------
    def list_files(self, folder_id: str, page_size: int = 100) -> List[Dict[str, Any]]:
        try:
            results: List[Dict[str, Any]] = []
            page_token = None
            while True:
                response = self._execute_with_retry(
                    lambda: self.service.files()
                    .list(
                        q=f"'{folder_id}' in parents and trashed=false",
                        pageSize=page_size,
                        pageToken=page_token,
                        fields="nextPageToken, files(id, name, mimeType, modifiedTime, size, parents)",
                    )
                    .execute()
                )
                results.extend(response.get("files", []))
                page_token = response.get("nextPageToken")
                if not page_token:
                    break
            return results
        except HttpError as exc:
            raise DriveClientError(f"Failed to list files in folder {folder_id}: {exc}")

    def search_folders(self, query: str, page_size: int = 10) -> List[Dict[str, Any]]:
        try:
            safe_query = query.replace("'", "\\'")
            response = self.service.files().list(
                q=f"mimeType='{self.MIME_TYPES['folder']}' and name contains '{safe_query}' and trashed=false",
                spaces="drive",
                pageSize=page_size,
                fields="files(id, name, parents)",
            ).execute()
            return response.get("files", [])
        except HttpError as exc:
            raise DriveClientError(f"Failed to search folders: {exc}")

    def search_documents_and_sheets(self, query: str, page_size: int = 20) -> List[Dict[str, Any]]:
        """Search for Google Docs and Sheets by name substring."""
        try:
            safe_query = query.replace("'", "\\'")
            mime_filter = (
                f"(mimeType='{self.MIME_TYPES['document']}' or mimeType='{self.MIME_TYPES['spreadsheet']}')"
            )
            response = self.service.files().list(
                q=f"{mime_filter} and name contains '{safe_query}' and trashed=false",
                spaces="drive",
                pageSize=page_size,
                fields="files(id, name, mimeType, parents, modifiedTime)",
            ).execute()
            return response.get("files", [])
        except HttpError as exc:
            raise DriveClientError(f"Failed to search files: {exc}")

    def list_subfolders(self, folder_id: str) -> List[Dict[str, Any]]:
        try:
            response = self.service.files().list(
                q=f"'{folder_id}' in parents and mimeType='{self.MIME_TYPES['folder']}' and trashed=false",
                fields="files(id, name, parents)",
                pageSize=200,
            ).execute()
            return response.get("files", [])
        except HttpError as exc:
            raise DriveClientError(f"Failed to list subfolders: {exc}")

    def get_folder_path(self, folder_id: str, cache: Optional[Dict[str, Dict[str, Any]]] = None, ellipsis_threshold: int = 3) -> str:
        """Return a human-readable path, memoizing parent lookups to cut API calls.

        If the path depth exceeds `ellipsis_threshold`, compress the middle as "(...)".
        """
        cache = cache if cache is not None else {}
        parts: List[str] = []
        current = folder_id

        while current:
            if current in cache:
                meta = cache[current]
            else:
                meta = self.service.files().get(fileId=current, fields="id, name, parents").execute()
                cache[current] = meta

            parts.append(meta.get("name", ""))
            parents = meta.get("parents", [])
            if not parents:
                break
            current = parents[0]

        parts = list(reversed(parts))
        if len(parts) > ellipsis_threshold:
            return f"{parts[0]} ... > {parts[-1]}"
        return " > ".join(parts)

    # ---------- downloads ----------
    def export_google_doc(self, file_id: str) -> bytes:
        try:
            request = self.service.files().export_media(
                fileId=file_id, mimeType=self.EXPORT_FORMATS["document"]
            )
            content = io.BytesIO()
            downloader = MediaIoBaseDownload(content, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
            return content.getvalue()
        except HttpError as exc:
            raise DriveClientError(f"Failed to export Google Doc {file_id}: {exc}")

    def export_google_sheet(self, file_id: str) -> bytes:
        try:
            request = self.service.files().export_media(
                fileId=file_id, mimeType=self.EXPORT_FORMATS["spreadsheet"]
            )
            content = io.BytesIO()
            downloader = MediaIoBaseDownload(content, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
            return content.getvalue()
        except HttpError as exc:
            raise DriveClientError(f"Failed to export Google Sheet {file_id}: {exc}")

    def export_sheet_tab(self, file_id: str, sheet_id: int) -> bytes:
        try:
            from google.auth.transport.requests import AuthorizedSession

            authed_session = AuthorizedSession(self.service._http.credentials)
            url = f"https://docs.google.com/spreadsheets/d/{file_id}/export?format=csv&gid={sheet_id}"
            response = authed_session.get(url)
            response.raise_for_status()
            return response.content
        except Exception as exc:
            raise DriveClientError(f"Failed to export sheet tab {sheet_id} from {file_id}: {exc}")

    def get_sheet_tabs(self, file_id: str) -> List[Dict[str, Any]]:
        if not self.sheets_service:
            return [{"title": "Sheet1", "sheetId": 0, "index": 0}]
        try:
            spreadsheet = self._execute_with_retry(
                lambda: self.sheets_service.spreadsheets()
                .get(spreadsheetId=file_id, fields="sheets(properties(sheetId,title,index))")
                .execute()
            )
            sheets = []
            for sheet in spreadsheet.get("sheets", []):
                props = sheet.get("properties", {})
                sheets.append(
                    {
                        "title": props.get("title", "Sheet1"),
                        "sheetId": props.get("sheetId", 0),
                        "index": props.get("index", 0),
                    }
                )
            return sheets or [{"title": "Sheet1", "sheetId": 0, "index": 0}]
        except Exception as exc:
            print(f"     Warning: Could not get sheet tabs, using single export: {exc}")
            return [{"title": "Sheet1", "sheetId": 0, "index": 0}]

    def download_file(self, file_id: str) -> bytes:
        try:
            request = self.service.files().get_media(fileId=file_id)
            content = io.BytesIO()
            downloader = MediaIoBaseDownload(content, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
            return content.getvalue()
        except HttpError as exc:
            raise DriveClientError(f"Failed to download file {file_id}: {exc}")

    # ---------- uploads ----------
    def create_document(self, name: str, parent_id: str, html_content: str) -> Dict[str, Any]:
        media = MediaIoBaseUpload(io.BytesIO(html_content.encode("utf-8")), mimetype="text/html")
        body = {
            "name": name,
            "mimeType": self.MIME_TYPES["document"],
            "parents": [parent_id],
        }
        try:
            file = (
                self.service.files()
                .create(body=body, media_body=media, fields="id, name, modifiedTime")
                .execute()
            )
            return file
        except HttpError as exc:
            raise DriveClientError(f"Failed to create document '{name}': {exc}")

    def create_folder(self, name: str, parent_id: str) -> Dict[str, Any]:
        body = {
            "name": name,
            "mimeType": self.MIME_TYPES["folder"],
            "parents": [parent_id],
        }
        try:
            return self.service.files().create(body=body, fields="id, name, parents").execute()
        except HttpError as exc:
            raise DriveClientError(f"Failed to create folder '{name}': {exc}")

    def find_child_folder(self, parent_id: str, name: str) -> Optional[Dict[str, Any]]:
        try:
            response = self.service.files().list(
                q=(
                    f"'{parent_id}' in parents and "
                    f"mimeType='{self.MIME_TYPES['folder']}' and name='{name}' and trashed=false"
                ),
                fields="files(id, name, parents)",
                pageSize=1,
            ).execute()
            files = response.get("files", [])
            return files[0] if files else None
        except HttpError:
            return None

    # ---------- type helpers ----------
    def is_google_doc(self, mime_type: str) -> bool:
        return mime_type == self.MIME_TYPES["document"]

    def is_google_sheet(self, mime_type: str) -> bool:
        return mime_type == self.MIME_TYPES["spreadsheet"]

    def is_folder(self, mime_type: str) -> bool:
        return mime_type == self.MIME_TYPES["folder"]

    def is_supported_file(self, mime_type: str) -> bool:
        return self.is_google_doc(mime_type) or self.is_google_sheet(mime_type)

    # ---------- internals ----------
    def _execute_with_retry(self, func, max_retries: int = 3, initial_delay: float = 1.0):
        delay = initial_delay
        last_error: Optional[Exception] = None
        for attempt in range(max_retries):
            try:
                return func()
            except HttpError as exc:
                last_error = exc
                if exc.resp.status in [429, 500, 503] and attempt < max_retries - 1:
                    time.sleep(delay)
                    delay *= 2
                    continue
                raise
        if last_error:
            raise last_error

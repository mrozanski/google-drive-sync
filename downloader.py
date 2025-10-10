"""File download and conversion logic."""

import os
from pathlib import Path
from typing import Dict, Any, List
from drive_client import DriveClient


class DownloadError(Exception):
    """Raised when file download fails."""
    pass


class Downloader:
    """Handles downloading and converting files from Google Drive."""

    def __init__(self, drive_client: DriveClient, target_dir: Path):
        """Initialize downloader.

        Args:
            drive_client: Authenticated Drive client
            target_dir: Target directory for downloads
        """
        self.drive_client = drive_client
        self.target_dir = target_dir
        self.stats = {
            'docs': 0,
            'sheets': 0,
            'skipped': 0,
            'folders': 0,
            'errors': 0,
        }

    def download_folder(self, folder_id: str, current_path: Path = None) -> None:
        """Recursively download all supported files from a folder.

        Args:
            folder_id: Google Drive folder ID
            current_path: Current local path (defaults to target_dir)

        Raises:
            DownloadError: If download fails
        """
        if current_path is None:
            current_path = self.target_dir

        print(f"\n📁 Processing folder: {current_path}")

        try:
            # Get all files in this folder
            files = self.drive_client.list_files(folder_id)

            for file in files:
                file_name = file['name']
                file_id = file['id']
                mime_type = file['mimeType']

                if self.drive_client.is_folder(mime_type):
                    # Create subfolder and recurse
                    subfolder_path = current_path / file_name
                    subfolder_path.mkdir(parents=True, exist_ok=True)
                    self.stats['folders'] += 1
                    self.download_folder(file_id, subfolder_path)

                elif self.drive_client.is_google_doc(mime_type):
                    # Download and convert Google Doc
                    self._download_google_doc(file_id, file_name, current_path)

                elif self.drive_client.is_google_sheet(mime_type):
                    # Download and convert Google Sheet
                    self._download_google_sheet(file_id, file_name, current_path)

                else:
                    # Skip unsupported file types
                    print(f"  ⏭️  Skipping unsupported file: {file_name} ({mime_type})")
                    self.stats['skipped'] += 1

        except Exception as e:
            self.stats['errors'] += 1
            raise DownloadError(f"Failed to download folder {folder_id}: {e}")

    def _download_google_doc(self, file_id: str, file_name: str, target_path: Path) -> None:
        """Download and convert a Google Doc to Markdown.

        Args:
            file_id: Google Drive file ID
            file_name: Original file name
            target_path: Target directory path
        """
        try:
            print(f"  📄 Downloading Doc: {file_name}")
            content = self.drive_client.export_google_doc(file_id)

            # Save as .md file
            output_file = target_path / f"{file_name}.md"
            output_file.write_bytes(content)

            self.stats['docs'] += 1
            print(f"     ✓ Saved: {output_file.name}")

        except Exception as e:
            self.stats['errors'] += 1
            print(f"     ✗ Error downloading {file_name}: {e}")

    def _download_google_sheet(self, file_id: str, file_name: str, target_path: Path) -> None:
        """Download and convert a Google Sheet to CSV(s).

        For multi-sheet spreadsheets, exports each sheet as a separate CSV.

        Args:
            file_id: Google Drive file ID
            file_name: Original file name
            target_path: Target directory path
        """
        try:
            print(f"  📊 Downloading Sheet: {file_name}")

            # Get sheet tabs (Phase 1: single export)
            # In Phase 2, we'll add proper Sheets API support for multi-tab export
            sheets = self.drive_client.get_sheet_tabs(file_id)

            if len(sheets) == 1:
                # Single sheet - export as one CSV
                content = self.drive_client.export_google_sheet(file_id)
                output_file = target_path / f"{file_name}.csv"
                output_file.write_bytes(content)
                print(f"     ✓ Saved: {output_file.name}")
            else:
                # Multiple sheets - export each separately
                # Note: This is a placeholder for Phase 2
                # For now, we export the entire spreadsheet as one CSV
                content = self.drive_client.export_google_sheet(file_id)
                output_file = target_path / f"{file_name}.csv"
                output_file.write_bytes(content)
                print(f"     ✓ Saved: {output_file.name} (merged sheets)")
                print(f"     ℹ️  Multi-sheet export will be added in Phase 2")

            self.stats['sheets'] += 1

        except Exception as e:
            self.stats['errors'] += 1
            print(f"     ✗ Error downloading {file_name}: {e}")

    def print_summary(self) -> None:
        """Print download summary statistics."""
        print("\n" + "=" * 50)
        print("Download Summary:")
        print("=" * 50)
        print(f"  📄 Google Docs:    {self.stats['docs']}")
        print(f"  📊 Google Sheets:  {self.stats['sheets']}")
        print(f"  📁 Folders:        {self.stats['folders']}")
        print(f"  ⏭️  Skipped files:  {self.stats['skipped']}")
        if self.stats['errors'] > 0:
            print(f"  ✗ Errors:         {self.stats['errors']}")
        print("=" * 50)

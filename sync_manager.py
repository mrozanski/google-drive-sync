"""Sync manager for incremental synchronization."""

import os
import shutil
from pathlib import Path
from typing import Dict, Any, List, Set, Tuple
from datetime import datetime

from drive_client import DriveClient
from metadata import Metadata


class SyncError(Exception):
    """Raised when sync operations fail."""
    pass


class SyncManager:
    """Manages incremental synchronization between Drive and local directory."""

    def __init__(self, drive_client: DriveClient, target_dir: Path, metadata: Metadata):
        """Initialize sync manager.

        Args:
            drive_client: Authenticated Drive client
            target_dir: Target directory for sync
            metadata: Metadata manager
        """
        self.drive_client = drive_client
        self.target_dir = target_dir
        self.metadata = metadata
        self.deleted_dir = target_dir / "deleted-remotely"

        # Statistics
        self.stats = {
            'new': 0,
            'updated': 0,
            'deleted': 0,
            'unchanged': 0,
            'errors': 0,
            'folders': 0
        }

    def sync_folder(self, folder_id: str, current_path: Path = None,
                   drive_file_ids: Set[str] = None) -> None:
        """Recursively sync folder with incremental updates.

        Args:
            folder_id: Google Drive folder ID
            current_path: Current local path (defaults to target_dir)
            drive_file_ids: Set to collect all Drive file IDs (for deletion detection)

        Raises:
            SyncError: If sync fails
        """
        if current_path is None:
            current_path = self.target_dir

        if drive_file_ids is None:
            drive_file_ids = set()

        print(f"\n📁 Syncing folder: {current_path.relative_to(self.target_dir) or '.'}")

        try:
            # Get all files in this folder
            files = self.drive_client.list_files(folder_id)

            for file in files:
                file_name = file['name']
                file_id = file['id']
                mime_type = file['mimeType']
                modified_time = file['modifiedTime']

                # Track this file ID
                drive_file_ids.add(file_id)

                if self.drive_client.is_folder(mime_type):
                    # Create subfolder and recurse
                    subfolder_path = current_path / file_name
                    subfolder_path.mkdir(parents=True, exist_ok=True)
                    self.stats['folders'] += 1
                    self.sync_folder(file_id, subfolder_path, drive_file_ids)

                elif self.drive_client.is_supported_file(mime_type):
                    # Check if file needs syncing
                    if self.metadata.is_file_changed(file_id, modified_time):
                        self._sync_file(file, current_path)
                    else:
                        print(f"  ⏭️  Unchanged: {file_name}")
                        self.stats['unchanged'] += 1

                else:
                    # Skip unsupported file types (we only sync Google Docs and Sheets)
                    print(f"  ⏭️  Skipping unsupported file: {file_name} ({mime_type})")
                    self.stats['unchanged'] += 1

        except Exception as e:
            self.stats['errors'] += 1
            raise SyncError(f"Failed to sync folder {folder_id}: {e}")

    def handle_deletions(self, drive_file_ids: Set[str]) -> None:
        """Handle files that were deleted from Drive.

        Args:
            drive_file_ids: Set of all current file IDs from Drive
        """
        deleted_files = self.metadata.get_deleted_files(drive_file_ids)

        if not deleted_files:
            return

        print(f"\n🗑️  Processing {len(deleted_files)} deleted file(s)...")

        # Create deleted directory if needed
        if deleted_files:
            self.deleted_dir.mkdir(parents=True, exist_ok=True)

        for file_id, meta in deleted_files.items():
            try:
                self._move_to_deleted(file_id, meta)
            except Exception as e:
                print(f"  ✗ Error moving deleted file: {e}")
                self.stats['errors'] += 1

    def _sync_file(self, file: Dict[str, Any], current_path: Path) -> None:
        """Sync a Google Workspace file (Doc or Sheet).

        Args:
            file: File metadata from Drive
            current_path: Current local path
        """
        file_id = file['id']
        file_name = file['name']
        mime_type = file['mimeType']
        modified_time = file['modifiedTime']

        is_new = self.metadata.get_file(file_id) is None
        action = "New" if is_new else "Updated"

        try:
            if self.drive_client.is_google_doc(mime_type):
                self._sync_google_doc(file_id, file_name, current_path)
                rel_path = str((current_path / f"{file_name}.md").relative_to(self.target_dir))

            elif self.drive_client.is_google_sheet(mime_type):
                self._sync_google_sheet(file_id, file_name, current_path)
                rel_path = str((current_path / f"{file_name}.csv").relative_to(self.target_dir))

            else:
                return

            # Update metadata
            file_type = 'doc' if self.drive_client.is_google_doc(mime_type) else 'sheet'
            self.metadata.add_file(file_id, rel_path, modified_time, file_type)

            if is_new:
                self.stats['new'] += 1
            else:
                self.stats['updated'] += 1

        except Exception as e:
            print(f"  ✗ Error syncing {file_name}: {e}")
            self.stats['errors'] += 1

    def _sync_google_doc(self, file_id: str, file_name: str, target_path: Path) -> None:
        """Sync a Google Doc to Markdown.

        Args:
            file_id: Google Drive file ID
            file_name: Original file name
            target_path: Target directory path
        """
        print(f"  📄 Syncing Doc: {file_name}")
        content = self.drive_client.export_google_doc(file_id)

        output_file = target_path / f"{file_name}.md"
        output_file.write_bytes(content)

        print(f"     ✓ Saved: {output_file.name}")

    def _sync_google_sheet(self, file_id: str, file_name: str, target_path: Path) -> None:
        """Sync a Google Sheet to CSV(s).

        For multi-sheet spreadsheets, exports each sheet as separate CSV.

        Args:
            file_id: Google Drive file ID
            file_name: Original file name
            target_path: Target directory path
        """
        print(f"  📊 Syncing Sheet: {file_name}")

        # Get all sheet tabs
        sheets = self.drive_client.get_sheet_tabs(file_id)

        if len(sheets) == 1:
            # Single sheet - export as one CSV
            content = self.drive_client.export_google_sheet(file_id)
            output_file = target_path / f"{file_name}.csv"
            output_file.write_bytes(content)
            print(f"     ✓ Saved: {output_file.name}")
        else:
            # Multiple sheets - export each separately
            print(f"     Found {len(sheets)} sheets, exporting individually...")
            for sheet in sheets:
                sheet_title = sheet['title']
                sheet_id = sheet['sheetId']

                # Export this specific sheet
                try:
                    content = self.drive_client.export_sheet_tab(file_id, sheet_id)
                    output_file = target_path / f"{file_name}-{sheet_title}.csv"
                    output_file.write_bytes(content)
                    print(f"     ✓ Saved: {output_file.name}")
                except Exception as e:
                    print(f"     ✗ Error exporting sheet '{sheet_title}': {e}")

    def _move_to_deleted(self, file_id: str, meta: Dict[str, Any]) -> None:
        """Move a deleted file to deleted-remotely folder.

        Args:
            file_id: Google Drive file ID
            meta: File metadata
        """
        original_path = self.target_dir / meta['path']

        if not original_path.exists():
            # File already gone locally
            self.metadata.remove_file(file_id)
            return

        file_name = original_path.name
        target_path = self.deleted_dir / file_name

        # Handle duplicate names
        target_path = self._get_unique_path(target_path)

        # Move file
        shutil.move(str(original_path), str(target_path))
        print(f"  🗑️  Moved to deleted: {file_name} → {target_path.name}")

        # Remove from metadata
        self.metadata.remove_file(file_id)
        self.stats['deleted'] += 1

    def _get_unique_path(self, path: Path) -> Path:
        """Get unique path by adding (2), (3), etc. if file exists.

        Args:
            path: Original path

        Returns:
            Unique path that doesn't exist
        """
        if not path.exists():
            return path

        stem = path.stem
        suffix = path.suffix
        counter = 2

        while True:
            new_path = path.parent / f"{stem} ({counter}){suffix}"
            if not new_path.exists():
                return new_path
            counter += 1

    def print_summary(self) -> None:
        """Print sync summary statistics."""
        print("\n" + "=" * 50)
        print("Sync Summary:")
        print("=" * 50)
        print(f"  ✨ New files:      {self.stats['new']}")
        print(f"  🔄 Updated files:  {self.stats['updated']}")
        print(f"  🗑️  Deleted files:  {self.stats['deleted']}")
        print(f"  ⏭️  Unchanged:      {self.stats['unchanged']}")
        print(f"  📁 Folders:        {self.stats['folders']}")
        if self.stats['errors'] > 0:
            print(f"  ✗ Errors:         {self.stats['errors']}")
        print("=" * 50)

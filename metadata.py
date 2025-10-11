"""Metadata management for tracking sync state."""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional


class MetadataError(Exception):
    """Raised when metadata operations fail."""
    pass


class Metadata:
    """Manages sync metadata for tracking file states."""

    def __init__(self, target_dir: Path):
        """Initialize metadata manager.

        Args:
            target_dir: Target directory containing .gdrive-sync folder
        """
        self.target_dir = target_dir
        self.sync_dir = target_dir / ".gdrive-sync"
        self.metadata_file = self.sync_dir / "metadata.json"
        self.data = self._load()

    def _load(self) -> Dict[str, Any]:
        """Load metadata from file or create new.

        Returns:
            Metadata dictionary
        """
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Warning: Could not load metadata: {e}")
                print("Starting with fresh metadata")
                return self._create_empty()
        else:
            return self._create_empty()

    def _create_empty(self) -> Dict[str, Any]:
        """Create empty metadata structure.

        Returns:
            Empty metadata dictionary
        """
        return {
            "version": "2.0",
            "last_sync": None,
            "files": {}
        }

    def save(self) -> None:
        """Save metadata to file.

        Raises:
            MetadataError: If save fails
        """
        try:
            # Ensure sync directory exists
            self.sync_dir.mkdir(parents=True, exist_ok=True)

            # Update last sync time
            self.data["last_sync"] = datetime.now().isoformat()

            # Write metadata
            with open(self.metadata_file, 'w') as f:
                json.dump(self.data, f, indent=2)

        except Exception as e:
            raise MetadataError(f"Failed to save metadata: {e}")

    def add_file(self, file_id: str, path: str, modified_time: str,
                 file_type: str, size: Optional[int] = None) -> None:
        """Add or update file metadata.

        Args:
            file_id: Google Drive file ID
            path: Relative path from target directory
            modified_time: ISO format modified time from Drive
            file_type: File type (doc, sheet, file)
            size: File size in bytes (optional)
        """
        self.data["files"][file_id] = {
            "path": path,
            "modified_time": modified_time,
            "type": file_type,
            "size": size,
            "last_synced": datetime.now().isoformat()
        }

    def get_file(self, file_id: str) -> Optional[Dict[str, Any]]:
        """Get file metadata by ID.

        Args:
            file_id: Google Drive file ID

        Returns:
            File metadata or None if not found
        """
        return self.data["files"].get(file_id)

    def remove_file(self, file_id: str) -> Optional[Dict[str, Any]]:
        """Remove file from metadata.

        Args:
            file_id: Google Drive file ID

        Returns:
            Removed file metadata or None if not found
        """
        return self.data["files"].pop(file_id, None)

    def get_all_files(self) -> Dict[str, Dict[str, Any]]:
        """Get all tracked files.

        Returns:
            Dictionary of file_id -> metadata
        """
        return self.data["files"]

    def is_file_changed(self, file_id: str, drive_modified_time: str) -> bool:
        """Check if file has changed since last sync.

        Args:
            file_id: Google Drive file ID
            drive_modified_time: Current modified time from Drive (ISO format)

        Returns:
            True if file is new or modified, False if unchanged
        """
        file_meta = self.get_file(file_id)
        if not file_meta:
            # New file
            return True

        # Compare modified times
        return file_meta["modified_time"] != drive_modified_time

    def get_deleted_files(self, current_drive_ids: set) -> Dict[str, Dict[str, Any]]:
        """Find files that exist in metadata but not in Drive.

        Args:
            current_drive_ids: Set of current file IDs from Drive

        Returns:
            Dictionary of deleted file_id -> metadata
        """
        deleted = {}
        for file_id, meta in self.data["files"].items():
            if file_id not in current_drive_ids:
                deleted[file_id] = meta
        return deleted

    def get_last_sync_time(self) -> Optional[str]:
        """Get last sync timestamp.

        Returns:
            ISO format timestamp or None if never synced
        """
        return self.data.get("last_sync")

    def clear(self) -> None:
        """Clear all metadata (for force full sync)."""
        self.data = self._create_empty()

"""Metadata management for tracking sync state (v3.0)."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Set

DEFAULT_VERSION = "3.0"


class MetadataError(Exception):
    """Raised when metadata operations fail."""


class Metadata:
    """Manages sync metadata for tracking file states."""

    def __init__(self, target_dir: Path):
        self.target_dir = target_dir
        self.sync_dir = target_dir / ".gdrive-sync"
        self.metadata_file = self.sync_dir / "metadata.json"
        self.data = self._load()

    def _load(self) -> Dict[str, Any]:
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, "r") as f:
                    data = json.load(f)
                return self._upgrade_if_needed(data)
            except Exception as exc:  # corrupt file
                print(f"Warning: Could not load metadata: {exc}. Starting fresh.")
                return self._create_empty()
        return self._create_empty()

    def _upgrade_if_needed(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure metadata matches v3 schema."""
        if data.get("version") == DEFAULT_VERSION:
            return data

        upgraded = self._create_empty()
        upgraded["last_sync"] = data.get("last_sync")
        upgraded["files"] = data.get("files", {})
        # best-effort carry over folder id if present in prior versions
        if "drive_folder_id" in data:
            upgraded["drive_folder_id"] = data.get("drive_folder_id")
            upgraded["drive_folder_name"] = data.get("drive_folder_name")
            upgraded["drive_folder_path"] = data.get("drive_folder_path")
        return upgraded

    def _create_empty(self) -> Dict[str, Any]:
        return {
            "version": DEFAULT_VERSION,
            "drive_folder_id": None,
            "drive_folder_name": None,
            "drive_folder_path": None,
            "last_sync": None,
            "files": {},
        }

    def set_drive_folder(self, folder_id: str, name: str, path: str) -> None:
        self.data["drive_folder_id"] = folder_id
        self.data["drive_folder_name"] = name
        self.data["drive_folder_path"] = path

    def save(self) -> None:
        try:
            self.sync_dir.mkdir(parents=True, exist_ok=True)
            self.data["last_sync"] = datetime.utcnow().isoformat()
            with open(self.metadata_file, "w") as f:
                json.dump(self.data, f, indent=2)
        except Exception as exc:
            raise MetadataError(f"Failed to save metadata: {exc}")

    def add_file(self, file_id: str, path: str, modified_time: str, file_type: str,
                 size: Optional[int] = None) -> None:
        self.data["files"][file_id] = {
            "path": path,
            "modified_time": modified_time,
            "type": file_type,
            "size": size,
            "last_synced": datetime.utcnow().isoformat(),
        }

    def get_file(self, file_id: str) -> Optional[Dict[str, Any]]:
        return self.data["files"].get(file_id)

    def remove_file(self, file_id: str) -> Optional[Dict[str, Any]]:
        return self.data["files"].pop(file_id, None)

    def get_all_files(self) -> Dict[str, Dict[str, Any]]:
        return self.data["files"]

    def is_file_changed(self, file_id: str, drive_modified_time: str) -> bool:
        file_meta = self.get_file(file_id)
        if not file_meta:
            return True
        return file_meta.get("modified_time") != drive_modified_time

    def get_deleted_files(self, current_drive_ids: Set[str]) -> Dict[str, Dict[str, Any]]:
        deleted = {}
        for file_id, meta in self.data["files"].items():
            if file_id not in current_drive_ids:
                deleted[file_id] = meta
        return deleted

    def get_last_sync_time(self) -> Optional[str]:
        return self.data.get("last_sync")

    def clear(self) -> None:
        self.data = self._create_empty()

    # Convenience helpers
    def tracked_paths(self) -> Set[str]:
        return {meta.get("path") for meta in self.data.get("files", {}).values()}

    def drive_folder_id(self) -> Optional[str]:
        return self.data.get("drive_folder_id")

    def drive_folder_display(self) -> str:
        path = self.data.get("drive_folder_path")
        name = self.data.get("drive_folder_name")
        return path or name or "Unknown"

"""Sync manager for incremental synchronization."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Dict, Any, Set

from gdrive_sync.drive_client import DriveClient
from gdrive_sync.metadata import Metadata


class SyncError(Exception):
    """Raised when sync operations fail."""


class SyncManager:
    """Manages incremental synchronization between Drive and local directory."""

    def __init__(self, drive_client: DriveClient, target_dir: Path, metadata: Metadata):
        self.drive_client = drive_client
        self.target_dir = target_dir
        self.metadata = metadata
        self.deleted_dir = target_dir / "deleted-remotely"
        self.stats = {
            "new": 0,
            "updated": 0,
            "moved": 0,
            "deleted": 0,
            "unchanged": 0,
            "errors": 0,
            "folders": 0,
        }

    def sync_folder(self, folder_id: str, current_path: Path | None = None,
                    drive_file_ids: Set[str] | None = None) -> None:
        if current_path is None:
            current_path = self.target_dir
        if drive_file_ids is None:
            drive_file_ids = set()

        print(f"\n📁 Syncing folder: {current_path.relative_to(self.target_dir) if current_path != self.target_dir else '.'}")
        try:
            files = self.drive_client.list_files(folder_id)
            for file in files:
                file_name = file["name"]
                file_id = file["id"]
                mime_type = file["mimeType"]
                modified_time = file["modifiedTime"]
                drive_file_ids.add(file_id)

                if self.drive_client.is_folder(mime_type):
                    subfolder_path = current_path / file_name
                    subfolder_path.mkdir(parents=True, exist_ok=True)
                    self.stats["folders"] += 1
                    self.sync_folder(file_id, subfolder_path, drive_file_ids)
                elif self.drive_client.is_supported_file(mime_type):
                    needs_sync = self.metadata.is_file_changed(file_id, modified_time)
                    has_moved = self._check_if_file_moved(file_id, file_name, current_path)

                    if needs_sync:
                        self._sync_file(file, current_path)
                    elif has_moved:
                        self._move_file(file, current_path)
                    else:
                        print(f"  ⏭️  Unchanged: {file_name}")
                        self.stats["unchanged"] += 1
                else:
                    print(f"  ⏭️  Skipping unsupported file: {file_name} ({mime_type})")
                    self.stats["unchanged"] += 1
        except Exception as exc:
            self.stats["errors"] += 1
            raise SyncError(f"Failed to sync folder {folder_id}: {exc}")

    def handle_deletions(self, drive_file_ids: Set[str]) -> None:
        deleted_files = self.metadata.get_deleted_files(drive_file_ids)
        if not deleted_files:
            return

        print(f"\n🗑️  Processing {len(deleted_files)} deleted file(s)...")
        self.deleted_dir.mkdir(parents=True, exist_ok=True)

        for file_id, meta in deleted_files.items():
            try:
                self._move_to_deleted(file_id, meta)
            except Exception as exc:
                print(f"  ✗ Error moving deleted file: {exc}")
                self.stats["errors"] += 1

    def _check_if_file_moved(self, file_id: str, file_name: str, current_path: Path) -> bool:
        file_meta = self.metadata.get_file(file_id)
        if not file_meta:
            return False

        file_type = file_meta.get("type")
        if file_type == "doc":
            expected_rel = str((current_path / f"{file_name}.md").relative_to(self.target_dir))
        elif file_type == "sheet":
            expected_rel = str((current_path / f"{file_name}.csv").relative_to(self.target_dir))
        else:
            expected_rel = str((current_path / file_name).relative_to(self.target_dir))

        return file_meta.get("path") != expected_rel

    def _move_file(self, file: Dict[str, Any], new_path: Path) -> None:
        file_id = file["id"]
        file_name = file["name"]
        modified_time = file["modifiedTime"]
        file_meta = self.metadata.get_file(file_id)
        if not file_meta:
            return

        try:
            old_rel_path = file_meta["path"]
            old_full_path = self.target_dir / old_rel_path
            file_type = file_meta.get("type")
            if file_type == "doc":
                new_file_name = f"{file_name}.md"
            elif file_type == "sheet":
                new_file_name = f"{file_name}.csv"
            else:
                new_file_name = file_name

            new_full_path = new_path / new_file_name
            new_rel_path = str(new_full_path.relative_to(self.target_dir))

            if old_full_path.exists():
                new_full_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(old_full_path), str(new_full_path))
                print(f"  📦 Moved: {file_name}")
                print(f"     From: {old_rel_path}")
                print(f"     To: {new_rel_path}")

                if file_type == "sheet":
                    old_dir = old_full_path.parent
                    old_base = old_full_path.stem
                    for related_file in old_dir.glob(f"{old_base}-*.csv"):
                        sheet_suffix = related_file.name[len(old_base):]
                        new_related = new_full_path.parent / f"{new_full_path.stem}{sheet_suffix}"
                        shutil.move(str(related_file), str(new_related))
                        print(f"     Also moved: {related_file.name} → {new_related.name}")

                self.metadata.add_file(file_id, new_rel_path, modified_time, file_type)
                self.stats["moved"] += 1
            else:
                print(f"  ⚠️  File moved but not found locally, re-syncing: {file_name}")
                self._sync_file(file, new_path)
        except Exception as exc:
            print(f"  ✗ Error moving {file_name}: {exc}")
            self.stats["errors"] += 1

    def _sync_file(self, file: Dict[str, Any], current_path: Path) -> None:
        file_id = file["id"]
        file_name = file["name"]
        mime_type = file["mimeType"]
        modified_time = file["modifiedTime"]
        is_new = self.metadata.get_file(file_id) is None

        try:
            if self.drive_client.is_google_doc(mime_type):
                self._sync_google_doc(file_id, file_name, current_path)
                rel_path = str((current_path / f"{file_name}.md").relative_to(self.target_dir))
                file_type = "doc"
            elif self.drive_client.is_google_sheet(mime_type):
                self._sync_google_sheet(file_id, file_name, current_path)
                rel_path = str((current_path / f"{file_name}.csv").relative_to(self.target_dir))
                file_type = "sheet"
            else:
                return

            self.metadata.add_file(file_id, rel_path, modified_time, file_type)
            if is_new:
                self.stats["new"] += 1
            else:
                self.stats["updated"] += 1
        except Exception as exc:
            print(f"  ✗ Error syncing {file_name}: {exc}")
            self.stats["errors"] += 1

    def _sync_google_doc(self, file_id: str, file_name: str, target_path: Path) -> None:
        print(f"  📄 Syncing Doc: {file_name}")
        content = self.drive_client.export_google_doc(file_id)
        output_file = target_path / f"{file_name}.md"
        output_file.write_bytes(content)
        print(f"     ✓ Saved: {output_file.name}")

    def _sync_google_sheet(self, file_id: str, file_name: str, target_path: Path) -> None:
        print(f"  📊 Syncing Sheet: {file_name}")
        sheets = self.drive_client.get_sheet_tabs(file_id)
        if len(sheets) == 1:
            content = self.drive_client.export_google_sheet(file_id)
            output_file = target_path / f"{file_name}.csv"
            output_file.write_bytes(content)
            print(f"     ✓ Saved: {output_file.name}")
        else:
            print(f"     Found {len(sheets)} sheets, exporting individually...")
            for sheet in sheets:
                sheet_title = sheet["title"]
                sheet_id = sheet["sheetId"]
                try:
                    content = self.drive_client.export_sheet_tab(file_id, sheet_id)
                    output_file = target_path / f"{file_name}-{sheet_title}.csv"
                    output_file.write_bytes(content)
                    print(f"     ✓ Saved: {output_file.name}")
                except Exception as exc:
                    print(f"     ✗ Error exporting sheet '{sheet_title}': {exc}")

    def _move_to_deleted(self, file_id: str, meta: Dict[str, Any]) -> None:
        original_path = self.target_dir / meta["path"]
        if not original_path.exists():
            self.metadata.remove_file(file_id)
            return

        target_path = self._get_unique_path(self.deleted_dir / original_path.name)
        shutil.move(str(original_path), str(target_path))
        print(f"  🗑️  Moved to deleted: {original_path.name} → {target_path.name}")
        self.metadata.remove_file(file_id)
        self.stats["deleted"] += 1

    def _get_unique_path(self, path: Path) -> Path:
        if not path.exists():
            return path
        stem, suffix = path.stem, path.suffix
        counter = 2
        while True:
            candidate = path.parent / f"{stem} ({counter}){suffix}"
            if not candidate.exists():
                return candidate
            counter += 1

    def print_summary(self) -> None:
        print("\n" + "=" * 50)
        print("Sync Summary:")
        print("=" * 50)
        print(f"  ✨ New files:      {self.stats['new']}")
        print(f"  🔄 Updated files:  {self.stats['updated']}")
        print(f"  📦 Moved files:    {self.stats['moved']}")
        print(f"  🗑️  Deleted files:  {self.stats['deleted']}")
        print(f"  ⏭️  Unchanged:      {self.stats['unchanged']}")
        print(f"  📁 Folders:        {self.stats['folders']}")
        if self.stats["errors"] > 0:
            print(f"  ✗ Errors:         {self.stats['errors']}")
        print("=" * 50)

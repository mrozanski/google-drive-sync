"""Upload local Markdown files to Google Drive as Google Docs."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import List

import markdown

from gdrive_sync.drive_client import DriveClient
from gdrive_sync.metadata import Metadata


class UploadError(Exception):
    """Raised when upload operations fail."""


class Uploader:
    def __init__(self, drive_client: DriveClient, metadata: Metadata, root: Path):
        self.drive_client = drive_client
        self.metadata = metadata
        self.root = root
        folder_id = metadata.drive_folder_id()
        if not folder_id:
            raise UploadError("Drive folder not configured; run init first.")
        self.root_drive_folder_id = folder_id

    def find_untracked_markdown(self) -> List[Path]:
        tracked_paths = self.metadata.tracked_paths()
        candidates = []
        for path in self.root.rglob("*.md"):
            if ".gdrive-sync" in path.parts:
                continue
            rel = str(path.relative_to(self.root))
            if rel not in tracked_paths:
                candidates.append(path)
        return candidates

    def upload_all(self) -> List[str]:
        uploaded_ids: List[str] = []
        for path in self.find_untracked_markdown():
            parent_id = self._ensure_remote_parent(path.parent)
            html = markdown.markdown(path.read_text())
            doc = self.drive_client.create_document(path.stem, parent_id, html)
            modified = doc.get("modifiedTime", datetime.utcnow().isoformat())
            rel_path = str(path.relative_to(self.root))
            self.metadata.add_file(doc["id"], rel_path, modified, "doc")
            uploaded_ids.append(doc["id"])
            print(f"Uploaded {rel_path} → {doc['id']}")
        if uploaded_ids:
            self.metadata.save()
        return uploaded_ids

    def _ensure_remote_parent(self, local_parent: Path) -> str:
        if local_parent == self.root:
            return self.root_drive_folder_id
        relative = local_parent.relative_to(self.root)
        current_id = self.root_drive_folder_id
        for part in relative.parts:
            existing = self.drive_client.find_child_folder(current_id, part)
            if existing:
                current_id = existing["id"]
            else:
                created = self.drive_client.create_folder(part, current_id)
                current_id = created["id"]
        return current_id

"""Status detection for interactive CLI."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Set

from rich.console import Console
from rich.table import Table

from gdrive_sync.drive_client import DriveClient
from gdrive_sync.metadata import Metadata


@dataclass
class StatusReport:
    drive_folder_name: str
    remote_new: List[Dict]
    remote_modified: List[Dict]
    remote_deleted: List[Dict]
    local_untracked: List[Path]

    def display(self) -> None:
        console = Console()
        table = Table(title=f"Sync Status: {self.drive_folder_name}")
        table.add_column("Category")
        table.add_column("Count", justify="right")
        table.add_row("Remote: new", str(len(self.remote_new)))
        table.add_row("Remote: changed", str(len(self.remote_modified)))
        table.add_row("Remote: deleted", str(len(self.remote_deleted)))
        table.add_row("Local: new .md", str(len(self.local_untracked)))
        console.print(table)

        if self.local_untracked:
            console.print("\nLocal files to upload:")
            for path in self.local_untracked:
                console.print(f"  • {path}")


def collect_status(drive_client: DriveClient, metadata: Metadata, root: Path) -> StatusReport:
    folder_id = metadata.drive_folder_id()
    if not folder_id:
        raise ValueError("Metadata missing drive_folder_id; re-run init.")

    remote_files = _collect_drive_files(drive_client, folder_id)
    current_ids: Set[str] = {f["id"] for f in remote_files}
    remote_new = [f for f in remote_files if metadata.get_file(f["id"]) is None]
    remote_modified = [
        f
        for f in remote_files
        if metadata.get_file(f["id"]) is not None
        and metadata.is_file_changed(f["id"], f["modifiedTime"])
    ]
    remote_deleted = [
        {"id": file_id, **meta}
        for file_id, meta in metadata.get_deleted_files(current_ids).items()
    ]
    tracked_paths = metadata.tracked_paths()
    local_untracked = [
        path
        for path in _iter_markdown_files(root)
        if str(path.relative_to(root)) not in tracked_paths
    ]

    return StatusReport(
        drive_folder_name=metadata.drive_folder_display(),
        remote_new=remote_new,
        remote_modified=remote_modified,
        remote_deleted=remote_deleted,
        local_untracked=local_untracked,
    )


def _collect_drive_files(drive_client: DriveClient, folder_id: str, base_path: str = "") -> List[Dict]:
    entries: List[Dict] = []
    for file in drive_client.list_files(folder_id):
        mime = file["mimeType"]
        name = file["name"]
        if drive_client.is_folder(mime):
            entries.extend(
                _collect_drive_files(drive_client, file["id"], base_path + f"{name}/")
            )
        elif drive_client.is_supported_file(mime):
            ext = ".md" if drive_client.is_google_doc(mime) else ".csv"
            entries.append(
                {
                    "id": file["id"],
                    "path": base_path + name + ext,
                    "modifiedTime": file["modifiedTime"],
                    "type": "doc" if drive_client.is_google_doc(mime) else "sheet",
                }
            )
    return entries


def _iter_markdown_files(root: Path):
    for path in root.rglob("*.md"):
        if ".gdrive-sync" in path.parts:
            continue
        yield path

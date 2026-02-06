from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional
from datetime import datetime

import typer
from rich.console import Console

from gdrive_sync.auth import AuthenticationError, get_drive_service, get_sheets_service
from gdrive_sync.drive_client import DriveClient, DriveClientError
from gdrive_sync.folder_picker import pick_folder, pick_file
from gdrive_sync.global_config import GlobalConfig, GlobalConfigError
from gdrive_sync.interactive import (
    prompt_main_menu,
    prompt_uninitialized,
    prompt_overwrite_action,
)
from gdrive_sync.local_config import LocalConfig, find_local_root
from gdrive_sync.metadata import Metadata, MetadataError
from gdrive_sync.status import collect_status
from gdrive_sync.sync_manager import SyncError, SyncManager
from gdrive_sync.uploader import UploadError, Uploader

app = typer.Typer(help="Google Drive interactive sync CLI")
console = Console()


def _build_drive_client(global_config: GlobalConfig) -> DriveClient:
    drive_service = get_drive_service(global_config)
    sheets_service = get_sheets_service(global_config)
    return DriveClient(drive_service, sheets_service)


def _perform_init(root: Path, drive_client: DriveClient, metadata: Metadata, folder_id: Optional[str] = None) -> None:
    if folder_id:
        folder_id, folder_name, folder_path = _resolve_folder_info(drive_client, folder_id)
    else:
        folder_id, folder_name, folder_path = pick_folder(drive_client)
    metadata.set_drive_folder(folder_id, folder_name, folder_path)
    sync_manager = SyncManager(drive_client, root, metadata)
    drive_ids = set()
    sync_manager.sync_folder(folder_id, drive_file_ids=drive_ids)
    sync_manager.handle_deletions(drive_ids)
    metadata.save()
    sync_manager.print_summary()
    console.print("\nFolder initialized and files downloaded.")


def _ensure_local_config() -> LocalConfig:
    local = find_local_root()
    if not local:
        raise typer.BadParameter(
            "No .gdrive-sync metadata found in current or parent directories. Run `gdrive-sync init`."
        )
    return local


def _resolve_folder_info(drive_client: DriveClient, folder_id: str):
    meta = drive_client.service.files().get(fileId=folder_id, fields="id,name").execute()
    path = drive_client.get_folder_path(folder_id)
    return meta["id"], meta["name"], path


def _run_pull(local: LocalConfig, drive_client: DriveClient) -> None:
    metadata = local.load_metadata()
    sync_manager = SyncManager(drive_client, local.root, metadata)
    drive_ids = set()
    sync_manager.sync_folder(metadata.drive_folder_id(), drive_file_ids=drive_ids)
    sync_manager.handle_deletions(drive_ids)
    metadata.save()
    sync_manager.print_summary()


def _run_push(local: LocalConfig, drive_client: DriveClient) -> None:
    metadata = local.load_metadata()
    uploader = Uploader(drive_client, metadata, local.root)
    uploaded = uploader.upload_all()
    if uploaded:
        console.print(f"Uploaded {len(uploaded)} file(s).")
    else:
        console.print("No new markdown files to upload.")


def _run_sync(local: LocalConfig, drive_client: DriveClient) -> None:
    _run_pull(local, drive_client)
    _run_push(local, drive_client)


def _write_file_with_prompt(path: Path, content: bytes) -> bool:
    if path.exists():
        action = prompt_overwrite_action(path.name)
        if action == "Quit":
            return False
        if action == "Keep both (append timestamp)":
            timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
            path = path.with_name(f"{path.stem}-{timestamp}{path.suffix}")
    path.write_bytes(content)
    console.print(f"Saved {path}")
    return True


def _run_pull_file(output_dir: Path, drive_client: DriveClient) -> None:
    file = pick_file(drive_client)
    mime = file["mimeType"]
    name = file["name"]

    if drive_client.is_google_doc(mime):
        content = drive_client.export_google_doc(file["id"])
        target = output_dir / f"{name}.md"
        _write_file_with_prompt(target, content)
        return

    if drive_client.is_google_sheet(mime):
        sheets = drive_client.get_sheet_tabs(file["id"])
        if len(sheets) == 1:
            content = drive_client.export_google_sheet(file["id"])
            target = output_dir / f"{name}.csv"
            _write_file_with_prompt(target, content)
        else:
            for sheet in sheets:
                content = drive_client.export_sheet_tab(file["id"], sheet["sheetId"])
                target = output_dir / f"{name}-{sheet['title']}.csv"
                if not _write_file_with_prompt(target, content):
                    return
        return

    raise DriveClientError("Selected file is not a Google Doc or Sheet.")


@app.callback(invoke_without_command=True)
def entrypoint(
    ctx: typer.Context,
    pull: bool = typer.Option(False, "--pull", help="Download changes only"),
    push: bool = typer.Option(False, "--push", help="Upload local .md files only"),
    sync: bool = typer.Option(False, "--sync", help="Pull then push"),
    pull_file: bool = typer.Option(False, "--pull-file", help="One-off download of a single Drive Doc/Sheet"),
) -> None:
    if ctx.invoked_subcommand:
        return

    global_config = GlobalConfig()
    try:
        drive_client = _build_drive_client(global_config)
    except (AuthenticationError, GlobalConfigError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1)

    if pull_file:
        try:
            _run_pull_file(Path.cwd(), drive_client)
        except (DriveClientError, SyncError, UploadError, MetadataError) as exc:
            console.print(f"[red]{exc}[/red]")
            raise typer.Exit(code=1)
        return

    if pull or push or sync:
        local = _ensure_local_config()
        try:
            if sync:
                _run_sync(local, drive_client)
            elif pull:
                _run_pull(local, drive_client)
            elif push:
                _run_push(local, drive_client)
        except (SyncError, UploadError, MetadataError, DriveClientError) as exc:
            console.print(f"[red]{exc}[/red]")
            raise typer.Exit(code=1)
        return

    # Interactive mode
    local = find_local_root()
    if not local:
        if prompt_uninitialized():
            metadata = Metadata(Path.cwd())
            try:
                _perform_init(Path.cwd(), drive_client, metadata)
            except (DriveClientError, SyncError, MetadataError) as exc:
                console.print(f"[red]{exc}[/red]")
                raise typer.Exit(code=1)
        return

    metadata = local.load_metadata()
    status = collect_status(drive_client, metadata, local.root)
    choice = prompt_main_menu(status)
    try:
        if choice == "Sync (pull + push)":
            _run_sync(local, drive_client)
        elif choice == "Pull only (download changes)":
            _run_pull(local, drive_client)
        elif choice == "Push only (upload local files)":
            _run_push(local, drive_client)
        elif choice == "View details":
            status.display()
    except (SyncError, UploadError, MetadataError, DriveClientError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1)


@app.command()
def setup(credentials_file: Optional[Path] = typer.Option(
    None,
    help="Path to OAuth client credentials JSON; defaults to ./credentials.json if present",
)) -> None:
    global_config = GlobalConfig()
    source = credentials_file or Path("credentials.json")
    if not source.exists():
        console.print("Provide the credentials file with --credentials-file (download from Google Cloud Console).")
        raise typer.Exit(code=1)
    try:
        global_config.install_credentials(source)
        global_config.clear_token()
        console.print(f"Credentials stored at {global_config.credentials_path}. Token cache cleared.")
    except GlobalConfigError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1)


@app.command()
def init(
    folder_id: Optional[str] = typer.Option(None, "--folder-id", help="Google Drive folder id for non-interactive init"),
    local_root: Optional[Path] = None,
) -> None:
    root = (local_root or Path.cwd()).resolve()
    global_config = GlobalConfig()
    drive_client = _build_drive_client(global_config)
    metadata = Metadata(root)

    try:
        _perform_init(root, drive_client, metadata, folder_id=folder_id)
    except (DriveClientError, SyncError, MetadataError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1)


@app.command()
def status() -> None:
    global_config = GlobalConfig()
    drive_client = _build_drive_client(global_config)
    local = _ensure_local_config()
    metadata = local.load_metadata()
    report = collect_status(drive_client, metadata, local.root)
    report.display()


if __name__ == "__main__":  # pragma: no cover
    app()

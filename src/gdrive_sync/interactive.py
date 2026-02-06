"""Interactive menus powered by questionary."""
from __future__ import annotations

import questionary
from rich.console import Console

from gdrive_sync.status import StatusReport

console = Console()


def prompt_uninitialized() -> bool:
    console.print("This folder is not synced to Google Drive.\n")
    choice = questionary.select(
        "What would you like to do?",
        choices=[
            "Initialize sync with a Google Drive folder",
            "Exit",
        ],
    ).ask()
    return choice == "Initialize sync with a Google Drive folder"


def prompt_main_menu(status: StatusReport) -> str:
    status.display()
    console.print()
    choice = questionary.select(
        "What would you like to do?",
        choices=[
            "Sync (pull + push)",
            "Pull only (download changes)",
            "Push only (upload local files)",
            "View details",
            "Exit",
        ],
    ).ask()
    return choice or "Exit"


def prompt_folder_search() -> str:
    return questionary.text("Search for a Google Drive folder (Ctrl+C to exit):").ask()


def prompt_select_from_list(header: str, options: list[str]) -> str:
    return questionary.select(header, choices=[*options, "Exit"]).ask()


def confirm_selection(label: str) -> bool:
    return questionary.confirm(f"Selected: {label}\nConfirm?").ask()


def prompt_subfolder_choice(subfolders: list[str]) -> str:
    return questionary.select(
        "Select subfolder or '.' to use this folder",
        choices=[".", *subfolders, ".. (go back)"]
    ).ask()

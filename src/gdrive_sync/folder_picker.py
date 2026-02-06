"""Interactive Drive folder picker."""
from __future__ import annotations

from typing import Tuple

import questionary
import typer

from gdrive_sync.drive_client import DriveClient
from gdrive_sync.interactive import confirm_selection, prompt_folder_search, prompt_file_search


def pick_folder(drive_client: DriveClient) -> Tuple[str, str, str]:
    """Interactive folder search + navigation.

    Returns: (folder_id, folder_name, folder_path_display)
    """
    cache: dict = {}

    while True:
        query = prompt_folder_search()
        if not query:
            raise KeyboardInterrupt
        matches = drive_client.search_folders(query)
        if not matches:
            print(f"No folders found for '{query}'. Try again.")
            continue

        options = []
        for idx, folder in enumerate(matches, start=1):
            path = drive_client.get_folder_path(folder["id"], cache=cache)
            options.append({"name": f"{idx}. {folder['name']} ({path})", "value": folder})

        selection = questionary.select("Found folders:", choices=options + ["Search again", "Exit"]).ask()
        if selection == "Exit":
            raise typer.Exit(code=0)
        if not selection or selection == "Search again":
            continue

        # navigate subfolders
        current = selection
        while True:
            current_path = drive_client.get_folder_path(current["id"], cache=cache)
            subfolders = drive_client.list_subfolders(current["id"])
            choices = ["Use this folder (.)"]
            for sub in subfolders:
                choices.append({"name": sub["name"], "value": sub})
            choices.extend(["Search again", "Exit"])
            choice = questionary.select(
                f"Folder: {current_path}\nSelect subfolder or '.' to use this folder",
                choices=choices,
            ).ask()

            if choice == "Exit":
                raise typer.Exit(code=0)
            if choice == "Search again" or choice is None:
                break
            if choice == "Use this folder (.)":
                if confirm_selection(current_path):
                    return current["id"], current["name"], current_path
                else:
                    break
            current = choice

        # loop back to search again


def pick_file(drive_client: DriveClient) -> dict:
    """Interactive search + select a single Google Doc/Sheet."""
    cache: dict = {}
    while True:
        query = prompt_file_search()
        if not query:
            raise typer.Exit(code=0)
        matches = drive_client.search_documents_and_sheets(query)
        if not matches:
            print(f"No files found for '{query}'. Try again.")
            continue

        choices = []
        for idx, file in enumerate(matches, start=1):
            path = drive_client.get_folder_path(file["id"], cache=cache)
            choices.append({"name": f"{idx}. {file['name']} ({path})", "value": file})
        choices.extend(["Search again", "Exit"])
        selection = questionary.select("Found files:", choices=choices).ask()
        if selection == "Exit":
            raise typer.Exit(code=0)
        if selection == "Search again" or selection is None:
            continue
        return selection

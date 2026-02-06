"""Interactive Drive folder picker."""
from __future__ import annotations

from typing import Tuple

import questionary

from gdrive_sync.drive_client import DriveClient
from gdrive_sync.interactive import confirm_selection, prompt_folder_search


def pick_folder(drive_client: DriveClient) -> Tuple[str, str, str]:
    """Interactive folder search + navigation.

    Returns: (folder_id, folder_name, folder_path_display)
    """
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
            path = drive_client.get_folder_path(folder["id"])
            options.append({"name": f"{idx}. {folder['name']} ({path})", "value": folder})

        selection = questionary.select("Found folders:", choices=options + ["Search again"]).ask()
        if not selection or selection == "Search again":
            continue

        # navigate subfolders
        current = selection
        while True:
            current_path = drive_client.get_folder_path(current["id"])
            subfolders = drive_client.list_subfolders(current["id"])
            choices = ["Use this folder (.)"]
            for sub in subfolders:
                choices.append({"name": sub["name"], "value": sub})
            choices.append("Search again")
            choice = questionary.select(
                f"Folder: {current_path}\nSelect subfolder or '.' to use this folder",
                choices=choices,
            ).ask()

            if choice == "Search again" or choice is None:
                break
            if choice == "Use this folder (.)":
                if confirm_selection(current_path):
                    return current["id"], current["name"], current_path
                else:
                    break
            current = choice

        # loop back to search again

# Interactive CLI Feature Specification

**Status**: Ready for implementation
**Purpose**: Transform google-drive-sync into a globally-installable interactive CLI that works from any folder

---

## Summary

Transform the existing `.env`-based tool into a globally-installable CLI (`gdrive-sync`) that:
1. Runs from any folder on the machine
2. Detects if current folder is synced and shows appropriate options
3. Provides interactive folder picker for initialization
4. Supports bidirectional sync (pull from Drive + push local .md files)

---

## User Experience

### Command: `gdrive-sync`

**In uninitialized folder:**
```
This folder is not synced to Google Drive.

What would you like to do?
> Initialize sync with a Google Drive folder
  Exit
```

**In initialized folder:**
```
Sync Status: My Project Notes
Remote: 3 files changed
Local:  2 new .md files to upload

What would you like to do?
> Sync (pull + push)
  Pull only (download changes)
  Push only (upload local files)
  View details
  Exit
```

### Folder Picker (Search-first)
```
Search for a Google Drive folder: project notes

Found 5 matching folders:
  1. Project Notes (My Drive > Work)
  2. Project Notes Archive (My Drive > Archive)
  ...

Select folder [1-5] or 's' to search again: 1

Folder: Project Notes
Subfolders:
  1. 2024/
  2. 2025/
  .. (go back)

Select subfolder or '.' to use this folder: .

Selected: My Drive > Work > Project Notes
Confirm? [Y/n]: y

Downloading 15 files...
Done! Folder initialized.
```

### Non-Interactive Mode (Flags)
```bash
gdrive-sync              # Interactive mode
gdrive-sync --pull       # Download changes only
gdrive-sync --push       # Upload local .md files only
gdrive-sync --sync       # Pull then push
gdrive-sync init         # Interactive init
gdrive-sync init --folder-id=xxx  # Non-interactive init
gdrive-sync status       # Show status only
gdrive-sync setup        # First-time credential setup
```

---

## Configuration

### Global Config: `~/.config/gdrive-sync/`
```
~/.config/gdrive-sync/
├── credentials.json     # OAuth client credentials
├── token.json           # OAuth tokens
└── config.json          # Optional global settings
```

### Local Config: `.gdrive-sync/` (in synced folder)
```json
{
  "version": "3.0",
  "drive_folder_id": "1abc123...",
  "drive_folder_name": "Project Notes",
  "drive_folder_path": "My Drive > Work > Notes",
  "last_sync": "2025-01-15T10:30:00Z",
  "files": {
    "<drive_file_id>": {
      "path": "relative/path/file.md",
      "modified_time": "...",
      "type": "doc|sheet",
      "last_synced": "..."
    }
  }
}
```

Note: No `origin` field needed. Once uploaded, files are tracked identically to remote files.

---

## Upload Detection

- Any `.md` file **in the synced folder or subfolders** not tracked in metadata is a candidate for upload
- Recursively scans for untracked `.md` files (similar to `git add .`)
- Folder structure is mirrored on Drive (e.g., `notes/meeting.md` → `notes/meeting` doc in Drive)
- On push: convert markdown → HTML → Google Doc

## Upload Behavior: One-Time Handoff

**Key principle:** Drive is always the source of truth. Push is a one-time handoff.

Once a file is uploaded:
1. It receives a Drive file ID and is tracked in metadata **exactly like any remote file**
2. Future changes made in Google Drive sync down normally (overwriting local copy)
3. Local edits to the file are ignored/overwritten on next pull (same as any synced file)
4. No special treatment - the file becomes a normal "remote" document

This keeps the tool as a **one-way mirror (Drive → Local)** with push being an "add to Drive" operation, not bidirectional sync.

---

## Files to Create

| File | Purpose |
|------|---------|
| `src/gdrive_sync/__init__.py` | Package init |
| `src/gdrive_sync/cli.py` | Typer CLI entry point |
| `src/gdrive_sync/interactive.py` | Interactive menus (questionary) |
| `src/gdrive_sync/folder_picker.py` | Drive folder search/navigation |
| `src/gdrive_sync/global_config.py` | ~/.config/gdrive-sync/ management |
| `src/gdrive_sync/local_config.py` | .gdrive-sync/ folder detection |
| `src/gdrive_sync/status.py` | Change detection and status display |
| `src/gdrive_sync/uploader.py` | Upload .md as Google Docs |

## Files to Modify

| File | Changes |
|------|---------|
| `pyproject.toml` | Add `[project.scripts]`, new deps, src layout |
| `auth.py` | Use global credentials, add `drive.file` scope |
| `drive_client.py` | Add `search_folders()`, `list_subfolders()`, `create_document()` |
| `metadata.py` | Schema v3.0 with drive_folder_id |
| `sync_manager.py` | Minor updates for bidirectional tracking |

---

## New Dependencies

```toml
dependencies = [
    # Existing
    "google-api-python-client>=2.184.0",
    "google-auth-httplib2>=0.2.0",
    "google-auth-oauthlib>=1.2.2",
    # New
    "typer>=0.12.0",        # CLI framework
    "questionary>=2.0.0",   # Interactive prompts
    "rich>=13.0.0",         # Beautiful output
    "markdown>=3.5.0",      # For upload conversion
]
# Remove: python-dotenv (no longer needed)
```

---

## Implementation Phases

### Phase 1: Core Infrastructure
- Restructure as `src/gdrive_sync/` package
- Create `pyproject.toml` with `[project.scripts]` for global install
- Implement `global_config.py` (credentials management)
- Implement `local_config.py` (folder detection)
- Modify `auth.py` to use global credentials
- Create minimal `cli.py` with setup command

**Deliverable:** `gdrive-sync setup` works

### Phase 2: Interactive Initialization
- Implement `folder_picker.py` (search + navigation)
- Add Drive API methods: `search_folders()`, `list_subfolders()`, `get_folder_path()`
- Implement init command
- Update `metadata.py` to v3.0
- Download all files on initialization

**Deliverable:** `gdrive-sync` in new folder shows init wizard

### Phase 3: Status Detection and Interactive Sync
- Implement `status.py` (change detection)
- Implement `interactive.py` (menus)
- Integrate with existing `sync_manager.py` for pull
- Rich-formatted status display

**Deliverable:** `gdrive-sync` in initialized folder shows status + menu

### Phase 4: Upload Support (Push)
- Add `drive.file` scope to auth
- Implement `uploader.py` (markdown → Google Doc)
- Recursive scan for untracked `.md` files in folder tree
- Mirror folder structure on Drive when uploading
- Add `create_document()`, `create_folder()` to drive_client
- After upload, track file in metadata (same as remote files)

**Deliverable:** Push local files to Drive (one-time handoff)

### Phase 5: Non-Interactive Mode and Polish
- Implement `--pull`, `--push`, `--sync` flags
- Implement `--init --folder-id=xxx`
- Add `status` command
- Error handling, README update

**Deliverable:** Production-ready CLI

---

## OAuth Scopes

```python
SCOPES = [
    'https://www.googleapis.com/auth/drive.readonly',      # Read access
    'https://www.googleapis.com/auth/drive.file',          # Write to app-created files
    'https://www.googleapis.com/auth/spreadsheets.readonly'
]
```

Note: Adding `drive.file` requires re-authentication (delete existing token.json).

---

## Verification Plan

1. **Install globally:** `uv tool install .` from repo
2. **Setup:** Run `gdrive-sync setup` and provide credentials
3. **Initialize:** `cd ~/Documents/test && gdrive-sync` → init wizard
4. **Pull:** Make changes in Drive → `gdrive-sync --pull`
5. **Push:** Create local .md file → `gdrive-sync --push`
6. **Sync:** `gdrive-sync --sync` does both
7. **Interactive:** `gdrive-sync` shows status and menu

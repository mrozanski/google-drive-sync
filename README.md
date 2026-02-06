# gdrive-sync

Interactive, globally-installable CLI that syncs a Google Drive folder to a local directory. Pulls Google Docs/Sheets down as Markdown/CSV, and can push new local `.md` files up to Drive (one-time handoff).

## What's inside
- Interactive menus (`gdrive-sync`) for init/sync/status.
- Non-interactive flags: `--pull`, `--push`, `--sync`, `init --folder-id`, `status`.
- Folder picker with Drive search + subfolder navigation.
- Global config at `~/.config/gdrive-sync/` (credentials + token).
- Local metadata at `.gdrive-sync/metadata.json` (schema v3.0 with drive folder id/name/path).
- Push support: scans for untracked `.md`, converts to HTML → Google Docs, mirrors folder structure, then tracks like remote files.

## Requirements
- Python 3.13+ (project uses src layout)
- `uv` package manager
- Google Cloud project with Drive API + Sheets API enabled
- OAuth client credentials JSON (Desktop app)

## Install
```bash
uv tool install .
# creates ~/.local/bin/gdrive-sync (ensure it’s on PATH)
```
If you prefer a venv:
```bash
uv venv
source .venv/bin/activate
uv pip install -e .
```

## First-time setup (credentials)
1) In Google Cloud Console create OAuth client (Desktop) and download the JSON.  
2) Run:
```bash
gdrive-sync setup --credentials-file ./credentials.json
```
This copies the credentials to `~/.config/gdrive-sync/credentials.json` and clears any cached token. The first authenticated command will open a browser to grant scopes:
- `drive.readonly`
- `drive.file`
- `spreadsheets.readonly`

## Initialize a folder
From the directory you want to sync:
```bash
gdrive-sync          # interactive init wizard
```
You’ll search for a Drive folder, drill into subfolders, confirm, and the tool will download all supported files while creating `.gdrive-sync/metadata.json`.

Non-interactive:
```bash
gdrive-sync init --folder-id=<drive_folder_id>
```

## Everyday commands
- `gdrive-sync` : Interactive status + menu (sync/pull/push/view details).
- `gdrive-sync --pull` : Download remote changes only.
- `gdrive-sync --push` : Upload new local `.md` files only (one-time handoff).
- `gdrive-sync --sync` : Pull then push.
- `gdrive-sync status` : Show counts of remote new/changed/deleted and local untracked markdown.

## Push behavior (one-way handoff)
- Any untracked `.md` under the synced root is uploaded as a Google Doc, preserving relative folders by creating missing Drive folders.
- After upload, the file is tracked with its Drive ID like any remote file.
- Drive remains source of truth: later pulls overwrite local edits to uploaded files.

## Paths & config
- Global: `~/.config/gdrive-sync/{credentials.json, token.json, config.json}`
- Local (per repo): `.gdrive-sync/metadata.json`

## Troubleshooting
- “command not found”: ensure `~/.local/bin` is on your PATH or activate the venv.
- Auth issues: delete `~/.config/gdrive-sync/token.json` and rerun any command to re-auth.
- Re-point to another Drive folder: rerun `gdrive-sync init --folder-id=...` in the target directory (will refresh metadata and pull).

## Verification checklist
1) `uv tool install .`
2) `gdrive-sync setup --credentials-file ./credentials.json`
3) In a new folder: `gdrive-sync` → init wizard completes and downloads files.
4) Remote edits show up with `gdrive-sync --pull`.
5) New local `.md` uploads with `gdrive-sync --push`.
6) `gdrive-sync` shows interactive status/menu in an initialized folder.

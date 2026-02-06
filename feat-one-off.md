# Feature: one-off pull doc from gdrive

The user wants to be able to run a command from any location in the FS, use the CLI browsing feature to select a single file from Google Drive, confirm and get a local copy inm markdown (or CSV for sheets) in the current location. No tracking, just one time download of one custom selected file.

Starts with `gdrive-sync --pull-file`

The UX should start similarly to the interactive mode, but the search should be for a single file (currently it searches folder names). The user should be able to select the file and get a local copy in markdown (or CSV for sheets) in the current location. No tracking, just one time download of one custom selected file.

The search when not using the --pull-file flag should continue to work as it does now: search fodler names only.

Once the document is downloaded, the tool should exit.

If there is a local copy of the selected file, the tool should ask for confirmation with the folowing options:
- overwrite the local file
- keep both (append a timestamp to the new local copy)
- quit the tool


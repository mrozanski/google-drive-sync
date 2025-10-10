# Google Drive to iCloud Sync Project Plan

## Project Overview
Create a Python script that syncs a Google Drive project folder to a local iCloud directory with one-way synchronization, converting Google Workspace files to standard formats.

## Requirements
- **Source**: Google Drive project folder (specified folder and all subfolders)
- **Target**: Local iCloud Drive folder
- **Sync Direction**: One-way (Google Drive → iCloud, local changes overwritten)
- **File Conversions**:
  - Google Docs → Markdown (.md)
  - Google Sheets → CSV (.csv)
  - Regular files → Direct copy
- **Structure**: Preserve complete folder hierarchy
- **Performance**: Incremental sync (only changed files)

## Technical Implementation Plan

### 1. Authentication & Setup
- Create Google Cloud project and enable Drive API
- Set up OAuth2 credentials or service account
- Configuration file for:
  - Source Google Drive folder ID
  - Target iCloud directory path
  - Sync preferences
For the initial setup we'll use manual .env file editing. Include a check at start, if missing configuration, exit with error message. "Configuration missing" and when possible, include what wasn't found (the file, which property, which value)

Authentication Method: OAuth2 (user authentication)

  Rationale:
  - Personal sync tool accessing user's own Google Drive folders
  - No folder sharing setup required
  - Better security: tokens are revocable and auto-expire
  - Natural permission model (acts as the user)

  Token Lifecycle:
  - Initial browser authentication (one-time setup)
  - Access tokens expire ~1 hour, automatically refreshed using long-lived refresh token
  - Refresh tokens remain valid for months/years with regular use
  - Script runs automated without browser interaction after initial setup

  Failure Scenarios & Recovery:
  - Refresh tokens may fail if: manually revoked, Google password changed, suspicious activity detected, or unused for ~6 months
  - Remote re-authentication options: Screen Sharing/VNC (requires pre-configuration), authenticate on another device and transfer token.json, or SSH access for config changes
  - Mitigation strategy: Implement email/push notifications for auth failures, enable macOS Screen Sharing for remote access, use access_type='offline' in OAuth flow

  Future Enhancement:
  - Consider adding service account as fallback authentication method in later versions
  - Service account would enable headless re-authentication via SSH if OAuth fails

  Implementation Notes:
  - Request minimal scopes (read-only Drive access)
  - Implement robust error handling and graceful failure
  - Store tokens securely in local configuration directory
  - Regular script execution keeps refresh token active

### 2. Core Components

#### A. Drive API Integration
- **Endpoint**: `GET /drive/v3/files` with queries
- **Folder Discovery**: Recursive traversal using `parents in "folder_id"`
- **File Export**:
  - Google Docs: `files.export` with `mimeType='text/markdown'`
  - Google Sheets: `files.export` with `mimeType='text/csv'`
- **Regular Files**: `files.get` with `alt='media'`

#### B. Sync Logic
- Compare Drive `modifiedTime` with local file timestamps
- Build complete folder structure map
- Track processed files to handle deletions
- Skip unchanged files for performance

#### C. File System Operations
- Recreate folder structure in target directory
- Write converted files with appropriate extensions
- Handle file overwrites and deletions
- Maintain metadata for sync tracking

#### D. Logging and Metadata
Files structure: 
```
target_directory/
  ├── .gdrive-sync/
  │   ├── metadata.json    # Compact state (overwritten each run)
  │   └── sync.log         # Append-only history (with rotation)
```

In sync.log
* Append start run timestamp, total changes found to be synced (number of folders, files, new, updated, deleted), status of each folder and file sync once completed, end run timestamp.
* Include any errors in this log file too

### 3. Script Structure
```
google-drive-sync/
├── main.py              # Main sync script
├── auth.py              # Google Drive authentication
├── drive_client.py      # Drive API wrapper
├── file_converter.py    # File conversion utilities
├── sync_manager.py      # Sync logic and file management
├── config.py            # Configuration management
├── requirements.txt     # Python dependencies
└── README.md           # Setup and usage instructions
```

### 4. Key Features
- **Incremental Sync**: Only process changed files
- **Error Handling**: Robust error handling and retry logic
- **Logging**: Detailed logging for monitoring and debugging
- **Configuration**: Easy setup for different projects/folders
- **Automation Ready**: Designed for cron job execution

### 5. Dependencies
- `google-api-python-client` - Google Drive API
- `google-auth` - Authentication
- `python-dotenv` - Configuration management
- Standard library: `os`, `pathlib`, `json`, `datetime`, `logging`

### 6. Automation Setup
- Create launchd plist (macOS) or cron job for periodic execution
- Recommended frequency: Every 30 minutes to 2 hours
- Include logging and notification options

## Usage Flow
1. **Initial Setup**: Configure Google API credentials and folder paths
2. **First Run**: Complete folder structure discovery and file download
3. **Subsequent Runs**: Incremental sync of only changed files
4. **Monitoring**: Review logs for sync status and any issues

## Implementation Notes
- Handle Google Drive API rate limits
- Implement exponential backoff for retries
- Consider file size limits and timeouts
- Ensure proper handling of special characters in filenames
- Test with various file types and folder structures
- When a Google Sheet has multiple tabs/sheets export each sheet as separate CSV files (e.g., filename-sheet1.csv, filename-sheet2.csv
- Ignore all files in Google Drive that are not of Doc or Sheet type
- If a file is deleted from Google Drive move from the original location locally to a folder in the root of the local directory named "deleted-remotely" (create this folder when it doesn't exist). The parent folder where the file was originally is not relevant, all deleted files go in the deleted-remotely folder. If duplicated file names append a space and an incremental number between parenthesis before the file extension, example: "Meeting Notes (2).md"
- Since this is one-way sync (Drive → iCloud) simply ignore local modifications and always sync from Drive (Note for future version: room for improvement here, if this becomes an issue)

## Next Steps
1. Set up development environment
2. Create Google Cloud project and enable Drive API
3. Implement authentication and basic Drive API connection
4. Build folder discovery and file listing functionality
5. Implement file conversion and download logic
6. Add sync management and incremental update capabilities
7. Create automation and monitoring setup
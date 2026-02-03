Outdated - replaced by interactive-cli-spec.md

# Sync-Up Feature Specification

**Feature**: Local Markdown → Google Docs Upload
**Status**: Proposed (not yet implemented)
**Purpose**: Enable quick local note-taking with sync to Google Drive as formatted Docs
**Priority**: TBD based on usage patterns

---

## Overview

### Use Case
User wants to create quick markdown notes locally (in any text editor) and sync them up to Google Drive as formatted Google Docs, separate from the main down-sync workflow.

### Workflow
1. User creates `.md` files in `TARGET_DIRECTORY/_local/`
2. User runs `uv run main.py --sync-up` (or separate script)
3. Script prompts for destination folder in Drive for each file
4. Script converts markdown to HTML and uploads as formatted Google Doc
5. Local file is archived to `_local-uploaded/` to prevent re-upload
6. Down-sync ignores `_local/` and `_local-uploaded/` folders

### Benefits
- ✅ Fast local markdown editing (offline-capable)
- ✅ Formatted Google Docs in Drive (collaborative, shareable)
- ✅ Separation of quick notes from main sync workflow
- ✅ Best of both worlds: local speed + cloud features

---

## Technical Architecture

### Directory Structure

```
target_directory/
├── _local/                    # Write markdown files here
│   ├── meeting-notes.md
│   ├── todo.md
│   └── ideas.md
├── _local-uploaded/           # Archived after upload
│   ├── meeting-notes.md
│   └── todo.md
├── .gdrive-sync/
│   ├── metadata.json          # Down-sync tracking
│   ├── uploads.json           # Upload tracking (NEW)
│   └── sync.log
└── [regular synced files]
```

### New Files Required

```
google-drive-sync/
├── main.py                    # Add --sync-up flag
├── sync_up.py                 # NEW: Upload logic
├── folder_navigator.py        # NEW: Interactive folder selection
├── upload_tracker.py          # NEW: Track uploaded files
└── markdown_converter.py      # NEW: MD→HTML conversion
```

### Upload Tracking (`uploads.json`)

```json
{
  "version": "1.0",
  "uploads": [
    {
      "local_path": "_local/meeting-notes.md",
      "local_hash": "sha256:abc123...",
      "drive_id": "1xYz_GoogleDocId",
      "drive_folder_id": "1abc_FolderId",
      "drive_name": "Meeting Notes",
      "uploaded_at": "2025-10-10T14:30:00",
      "status": "uploaded",
      "archived_path": "_local-uploaded/meeting-notes.md"
    }
  ]
}
```

---

## Implementation Phases

### Phase 1: Basic Upload (MVP)
**Goal**: Simple one-way upload with manual folder selection

**Features**:
- Scan `_local/*.md` for new files
- Convert markdown → HTML → Google Doc
- Flat folder list (type number to select)
- Upload as formatted Google Doc
- Move to `_local-uploaded/` after upload
- Track uploads in `uploads.json`
- Ignore `_local/*` in down-sync

**Scope Changes**:
- Add scope: `https://www.googleapis.com/auth/drive.file` (write access)
- User must re-authenticate (delete `token.json`)

**Dependencies**:
```bash
uv add markdown
```

**Estimated Complexity**: Medium (2-3 hours)

### Phase 2: Enhanced UX
**Goal**: Better folder navigation and file management

**Features**:
- Hierarchical folder navigation (breadcrumbs, parent navigation)
- Search/filter folders by name
- Remember last used folder as default
- Update existing docs if markdown modified
- Batch upload multiple files to same folder
- Show Drive URL after upload

**Estimated Complexity**: Medium (3-4 hours)

### Phase 3: Advanced Features
**Goal**: Full bi-directional workflow

**Features**:
- Detect if uploaded doc was edited in Drive
- Optionally sync down changes to local markdown
- Conflict resolution (local vs Drive edits)
- Markdown extensions (tables, code highlighting)
- Image embedding (upload images separately)
- Custom templates for doc formatting

**Estimated Complexity**: High (6-8 hours)

---

## Technical Details

### Markdown to Google Docs Conversion

**Method**: Upload HTML via Drive API (automatic conversion to Docs)

```python
import markdown
import io
from googleapiclient.http import MediaIoBaseUpload

def upload_markdown_as_doc(service, md_path, folder_id, title):
    """Convert markdown to formatted Google Doc."""

    # Read markdown file
    with open(md_path, 'r', encoding='utf-8') as f:
        md_content = f.read()

    # Convert to HTML with extensions
    html = markdown.markdown(
        md_content,
        extensions=['extra', 'codehilite', 'tables', 'toc']
    )

    # Prepare file metadata
    file_metadata = {
        'name': title,
        'mimeType': 'application/vnd.google-apps.document',
        'parents': [folder_id]
    }

    # Upload as HTML (Drive converts to Docs)
    media = MediaIoBaseUpload(
        io.BytesIO(html.encode('utf-8')),
        mimetype='text/html',
        resumable=True
    )

    file = service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id, name, webViewLink'
    ).execute()

    return file
```

### Formatting Support

**Well-Supported**:
- ✅ Headings (H1-H6)
- ✅ Bold, italic, strikethrough
- ✅ Bullet lists, numbered lists
- ✅ Links (clickable)
- ✅ Blockquotes
- ✅ Horizontal rules
- ✅ Inline code (monospace)

**Partial Support**:
- ⚠️ Code blocks (monospace paragraph, no syntax highlighting)
- ⚠️ Tables (basic formatting, may need extension)

**Not Supported**:
- ❌ Images (would need separate upload + insertion)
- ❌ Advanced formatting (custom fonts, colors)

### Folder Navigation UX

**Interactive CLI Example**:
```
Found 3 new files to upload.

[1/3] Upload: meeting-notes.md

Select destination folder:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[Root] My Drive
  1. 📁 Projects/
  2. 📁 Personal/
  3. 📁 Archive/
  4. 📁 Team Shared/

Enter: number | 'n' new | 's' skip | 'q' quit
> 1

[Projects] My Drive > Projects
  1. 📁 2025/
  2. 📁 2024/
  3. 📄 Roadmap.doc
  .. (parent)

Enter: number | '.' select here | 's' skip
> 1

[2025] My Drive > Projects > 2025
  1. 📁 Q1/
  2. 📁 Q2/
  .. (parent)

Enter: number | '.' select here | 's' skip
> .

✓ Selected: My Drive > Projects > 2025

Upload as: "meeting-notes" [y/n/r(ename)]: y

⬆️  Uploading meeting-notes.md...
✓ Created: Meeting Notes
   URL: https://docs.google.com/document/d/1abc.../edit
✓ Archived: _local-uploaded/meeting-notes.md

[2/3] Upload: todo.md
...
```

---

## Edge Cases & Solutions

### 1. Name Collision
**Problem**: File with same name exists in target folder

**Solution**:
```
File "meeting" already exists in this folder.
  [o] Overwrite (replace existing doc)
  [r] Rename (upload as "meeting (2)")
  [u] Update (replace content, keep ID)
  [s] Skip this file
>
```

**Preferred**: [u] Update existing doc (preserves sharing/comments)

### 2. Bi-Directional Sync Loop
**Problem**: Upload `_local/notes.md` → creates Doc → down-sync exports as `notes.md`

**Solution**:
- Track uploaded files in `uploads.json`
- Down-sync checks if file originated from upload
- Option 1: Skip downloading uploaded docs
- Option 2: Download to `_remote/` folder instead
- **Recommended**: Archive to `_local-uploaded/` after upload, preventing loop

### 3. File Modified After Upload
**Problem**: User edits `_local/notes.md` after uploading

**Solution**:
```python
# Check if file was modified after upload
if file_hash != tracked_hash:
    print(f"File modified since upload on {upload_date}")
    choice = prompt("[u] Update existing doc | [c] Create new | [s] Skip")
```

**Track**: File hash in `uploads.json` to detect changes

### 4. Multiple Files Same Name
**Problem**: `_local/notes.md` and `_local/archive/notes.md`

**Solution**:
- Scan subdirectories of `_local/`
- Show relative path in prompts: `notes.md` vs `archive/notes.md`
- Suggest different Drive names based on path

### 5. Permission/Scope Issues
**Problem**: Read-only scope can't create files

**Solution**:
- Add new scope: `https://www.googleapis.com/auth/drive.file`
  - Can create/modify files created by app
  - Cannot access other user files (safer than full access)
- Display clear message:
  ```
  Sync-up requires additional permissions.
  Deleting token.json to re-authenticate...

  You'll be asked to grant:
  ✓ Read access to Drive (existing)
  ✓ Create/modify files in Drive (NEW)
  ```

### 6. Large Files
**Problem**: Very large markdown files (>5MB)

**Solution**:
- Use resumable upload (already in code above)
- Show progress bar for files >1MB
- Warn if file >10MB (may be slow)

### 7. Down-Sync Interference
**Problem**: Regular sync tries to process `_local/` folder

**Solution**:
```python
# In sync_manager.py
IGNORED_FOLDERS = ['_local', '_local-uploaded', '.gdrive-sync', 'deleted-remotely']

def should_ignore_path(path: Path) -> bool:
    """Check if path should be ignored during sync."""
    parts = path.parts
    return any(ignored in parts for ignored in IGNORED_FOLDERS)
```

### 8. Network Failure During Upload
**Problem**: Upload fails mid-process

**Solution**:
- Use resumable uploads (Drive API supports this)
- Don't archive local file until upload confirmed
- Log partial uploads for retry
- Show clear error and don't mark as uploaded

---

## API Requirements

### Additional Scopes Needed

**Current (Phase 2)**:
- `https://www.googleapis.com/auth/drive.readonly`
- `https://www.googleapis.com/auth/spreadsheets.readonly`

**Required for Sync-Up**:
- `https://www.googleapis.com/auth/drive.file` (create/modify app files)

**Alternative (less secure)**:
- `https://www.googleapis.com/auth/drive` (full access)

**Recommendation**: Use `drive.file` scope for better security

### API Calls Required

1. **List folders** (for navigation):
   ```python
   service.files().list(
       q="mimeType='application/vnd.google-apps.folder' and trashed=false",
       fields="files(id, name, parents)"
   )
   ```

2. **Search for existing file** (conflict detection):
   ```python
   service.files().list(
       q=f"name='{filename}' and '{folder_id}' in parents and trashed=false",
       fields="files(id, name)"
   )
   ```

3. **Create document** (upload):
   ```python
   service.files().create(
       body=file_metadata,
       media_body=media,
       fields='id, name, webViewLink'
   )
   ```

4. **Update existing document** (if overwriting):
   ```python
   service.files().update(
       fileId=existing_id,
       media_body=media
   )
   ```

---

## Command-Line Interface

### Option 1: Flag-Based (Recommended)

```bash
# Normal down-sync
uv run main.py

# Upload local markdown files
uv run main.py --sync-up

# Force re-upload all files
uv run main.py --sync-up --force
```

### Option 2: Separate Script

```bash
# Down-sync
uv run main.py

# Upload
uv run sync_up.py
```

### Option 3: Interactive Menu

```bash
uv run main.py

Google Drive Sync Tool
━━━━━━━━━━━━━━━━━━━━━━
1. Sync from Drive (download)
2. Sync to Drive (upload)
3. Both (sync both ways)
4. Exit

Select option [1-4]:
```

**Recommendation**: Option 1 (flag-based) - consistent with `--force-full`

---

## Configuration Changes

### New .env Options (Optional)

```bash
# Existing
GOOGLE_FOLDER_ID=1abc...
TARGET_DIRECTORY=~/iCloud/MyProject
GOOGLE_CREDENTIALS_FILE=./credentials.json

# New (optional)
SYNC_UP_FOLDER=_local              # Folder to scan for uploads
SYNC_UP_ARCHIVE=_local-uploaded    # Archive after upload
SYNC_UP_AUTO_FOLDER=                # Optional: auto-upload to this folder (skip prompts)
```

### .gdriveignore (New File)

```
# Folders to ignore during down-sync
_local/
_local-uploaded/
.DS_Store
*.tmp
```

---

## Testing Checklist

### Basic Functionality
- [ ] Upload single markdown file
- [ ] Upload multiple files
- [ ] Navigate folder hierarchy
- [ ] Convert markdown formatting correctly
- [ ] Archive uploaded files
- [ ] Track uploads in uploads.json
- [ ] Ignore _local/ during down-sync

### Edge Cases
- [ ] Name collision (file exists)
- [ ] Modified file after upload
- [ ] Network failure during upload
- [ ] Very large files (>5MB)
- [ ] Special characters in filename
- [ ] Empty markdown file
- [ ] Markdown with images (should warn)

### Integration
- [ ] Works with existing down-sync
- [ ] Re-authentication for new scope
- [ ] Both APIs enabled (Drive + Sheets)
- [ ] Metadata doesn't conflict
- [ ] Log file includes upload events

---

## User Documentation (Draft)

### Quick Start

```bash
# 1. Create local markdown files
mkdir ~/iCloud/MyProject/_local
echo "# My Note" > ~/iCloud/MyProject/_local/note.md

# 2. Upload to Drive
uv run main.py --sync-up

# 3. Follow prompts to select destination folder
# 4. Files uploaded and archived to _local-uploaded/
```

### Workflow

1. **Write notes locally** in `_local/` folder using any text editor
2. **Run sync-up** when ready to publish to Drive
3. **Select destination** folder for each file
4. **Files converted** to formatted Google Docs with headings, lists, links, etc.
5. **Local copies archived** to prevent re-upload
6. **Edit in Drive** for collaboration and sharing

### Tips

- Use standard markdown for best formatting
- Headings, lists, bold, italic all supported
- Code blocks become monospace text
- Images not supported (upload separately)
- Files archived after upload (not deleted)

---

## Future Enhancements (Phase 3+)

### Bi-Directional Sync
- Detect edits in Drive
- Download changes back to local markdown
- Conflict resolution UI
- Merge strategies

### Advanced Formatting
- Custom CSS for Google Docs
- Image upload and embedding
- Table formatting improvements
- Syntax highlighting for code blocks

### Automation
- Watch `_local/` folder for new files
- Auto-upload on file creation
- Scheduled uploads
- Desktop notifications

### Templates
- Pre-defined document templates
- Standard formatting profiles
- Metadata frontmatter support

---

## Decision Points

Before implementing, decide:

1. **Scope**: `drive.file` (safer) vs `drive` (simpler)?
2. **UI**: Flag-based, separate script, or interactive menu?
3. **Archive**: Move to `_local-uploaded/` or delete after upload?
4. **Conflicts**: Overwrite, rename, or update existing docs?
5. **Auto-folder**: Support default upload folder to skip prompts?
6. **Batch mode**: Upload all to same folder, or prompt per file?

---

## Notes

- This feature is **proposed** based on potential workflow
- Recommend **validating use case** before implementation (manual copy/paste first)
- If frequently needed, proceed with **Phase 1** (MVP)
- Estimated implementation time: **2-3 hours** for basic version
- Can be built incrementally without breaking existing functionality

---

**Status**: Specification complete, awaiting usage validation
**Next Step**: Monitor manual upload frequency to decide if automation is warranted
**Created**: 2025-10-10

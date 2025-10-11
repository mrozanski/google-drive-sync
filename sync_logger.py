"""Structured logging for sync operations."""

import os
from pathlib import Path
from datetime import datetime
from typing import Optional


class SyncLogger:
    """Manages structured logging to .gdrive-sync/sync.log."""

    def __init__(self, target_dir: Path):
        """Initialize sync logger.

        Args:
            target_dir: Target directory containing .gdrive-sync folder
        """
        self.target_dir = target_dir
        self.sync_dir = target_dir / ".gdrive-sync"
        self.log_file = self.sync_dir / "sync.log"
        self.current_session_start = None

        # Ensure sync directory exists
        self.sync_dir.mkdir(parents=True, exist_ok=True)

        # Rotate log if too large (keep last 100KB)
        self._rotate_if_needed()

    def _rotate_if_needed(self, max_size: int = 100_000) -> None:
        """Rotate log file if it exceeds max size.

        Args:
            max_size: Maximum log file size in bytes (default: 100KB)
        """
        if not self.log_file.exists():
            return

        file_size = self.log_file.stat().st_size
        if file_size > max_size:
            # Keep last 50% of the file
            with open(self.log_file, 'r') as f:
                lines = f.readlines()

            # Keep last half
            keep_lines = lines[len(lines)//2:]

            with open(self.log_file, 'w') as f:
                f.write("... [log rotated] ...\n\n")
                f.writelines(keep_lines)

    def log_sync_start(self, folder_id: str) -> None:
        """Log sync session start.

        Args:
            folder_id: Google Drive folder ID being synced
        """
        self.current_session_start = datetime.now()
        timestamp = self.current_session_start.strftime("%Y-%m-%d %H:%M:%S")

        message = f"\n{'='*60}\n"
        message += f"[{timestamp}] Sync Started\n"
        message += f"Folder ID: {folder_id}\n"
        message += f"{'='*60}\n"

        self._write(message)

    def log_sync_end(self, stats: dict) -> None:
        """Log sync session end with statistics.

        Args:
            stats: Statistics dictionary with counts
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        duration = ""

        if self.current_session_start:
            elapsed = datetime.now() - self.current_session_start
            duration = f" (Duration: {elapsed.total_seconds():.1f}s)"

        message = f"\n[{timestamp}] Sync Completed{duration}\n"
        message += f"  ✨ New files:      {stats.get('new', 0)}\n"
        message += f"  🔄 Updated files:  {stats.get('updated', 0)}\n"
        message += f"  🗑️  Deleted files:  {stats.get('deleted', 0)}\n"
        message += f"  ⏭️  Unchanged:      {stats.get('unchanged', 0)}\n"
        message += f"  📁 Folders:        {stats.get('folders', 0)}\n"

        if stats.get('errors', 0) > 0:
            message += f"  ✗ Errors:         {stats['errors']}\n"

        message += f"{'='*60}\n"

        self._write(message)

    def log_file_operation(self, operation: str, file_name: str,
                          success: bool = True, error: Optional[str] = None) -> None:
        """Log individual file operation.

        Args:
            operation: Operation type (new, updated, deleted, skipped)
            file_name: File name
            success: Whether operation succeeded
            error: Error message if failed
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if success:
            icon = {
                'new': '✨',
                'updated': '🔄',
                'deleted': '🗑️',
                'skipped': '⏭️'
            }.get(operation, '•')
            message = f"[{timestamp}] {icon} {operation.capitalize()}: {file_name}\n"
        else:
            message = f"[{timestamp}] ✗ Error ({operation}): {file_name}\n"
            if error:
                message += f"           {error}\n"

        self._write(message)

    def log_error(self, error: str, context: Optional[str] = None) -> None:
        """Log an error.

        Args:
            error: Error message
            context: Optional context information
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        message = f"[{timestamp}] ✗ ERROR: {error}\n"
        if context:
            message += f"           Context: {context}\n"

        self._write(message)

    def log_info(self, message: str) -> None:
        """Log informational message.

        Args:
            message: Info message
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._write(f"[{timestamp}] ℹ️  {message}\n")

    def _write(self, message: str) -> None:
        """Write message to log file.

        Args:
            message: Message to write
        """
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(message)
        except Exception as e:
            # If logging fails, print to console but don't crash
            print(f"Warning: Failed to write to log: {e}")

    def get_log_path(self) -> Path:
        """Get path to log file.

        Returns:
            Path to sync.log
        """
        return self.log_file

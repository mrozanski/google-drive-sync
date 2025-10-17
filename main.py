#!/usr/bin/env python3
"""Google Drive to iCloud Sync - Phase 2: Incremental Sync Tool

This tool syncs a Google Drive folder to a local directory with:
- Incremental sync (only changed files)
- Google Docs → Markdown (.md)
- Google Sheets → CSV (.csv) with multi-sheet support
- Deletion handling (moved to deleted-remotely/)
- Metadata tracking and structured logging

Note: Only Google Docs and Sheets are synced. Other file types are skipped.
"""

import sys
import argparse
from pathlib import Path

from config import load_config, ConfigError
from auth import get_drive_service, get_sheets_service, AuthenticationError
from drive_client import DriveClient, DriveClientError
from sync_manager import SyncManager, SyncError
from metadata import Metadata, MetadataError
from sync_logger import SyncLogger


def main():
    """Main entry point for the sync tool."""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description='Sync Google Drive folder to local directory'
    )
    parser.add_argument(
        '--force-full',
        action='store_true',
        help='Force full sync (ignore metadata, download everything)'
    )
    args = parser.parse_args()

    print("=" * 60)
    print("Google Drive to iCloud Sync - Phase 2")
    print("=" * 60)

    try:
        # Load configuration
        print("\n📋 Loading configuration...")
        config = load_config()
        print(f"   Source folder ID: {config.google_folder_id}")
        print(f"   Target directory: {config.target_directory}")

        # Initialize metadata and logger
        metadata = Metadata(config.target_directory)
        logger = SyncLogger(config.target_directory)

        if args.force_full:
            print("\n⚠️  Force full sync enabled - clearing metadata")
            metadata.clear()

        # Check if this is first sync
        last_sync = metadata.get_last_sync_time()
        if last_sync:
            print(f"   Last sync: {last_sync}")
        else:
            print("   First sync - will download all files")

        # Authenticate with Google Drive and Sheets
        print("\n🔐 Authenticating with Google APIs...")
        drive_service = get_drive_service(config.credentials_file, config.token_file)
        sheets_service = get_sheets_service(config.credentials_file, config.token_file)
        print("   ✓ Authentication successful")

        # Create Drive client with Sheets support
        drive_client = DriveClient(drive_service, sheets_service)

        # Create sync manager
        sync_manager = SyncManager(drive_client, config.target_directory, metadata)

        # Start sync
        print("\n🔄 Starting sync...")
        print(f"   Syncing: Google Docs and Sheets only\n")

        # Log sync start
        logger.log_sync_start(config.google_folder_id)

        # Collect all Drive file IDs for deletion detection
        drive_file_ids = set()

        # Sync folder recursively
        sync_manager.sync_folder(config.google_folder_id, drive_file_ids=drive_file_ids)

        # Handle deletions
        sync_manager.handle_deletions(drive_file_ids)

        # Save metadata
        metadata.save()

        # Print summary
        sync_manager.print_summary()

        # Log sync end
        logger.log_sync_end(sync_manager.stats)

        print("\n✨ Sync complete!")
        print(f"\nFiles synced to: {config.target_directory}")
        print(f"Log file: {logger.get_log_path()}")

        return 0

    except ConfigError as e:
        print(f"\n❌ Configuration Error:")
        print(f"   {e}")
        print(f"\nPlease create a .env file based on .env.example")
        return 1

    except AuthenticationError as e:
        print(f"\n❌ Authentication Error:")
        print(f"   {e}")
        print(f"\nNote: Phase 2 requires both Drive and Sheets API access.")
        print(f"If you see permission errors, delete token.json and re-authenticate.")
        return 1

    except (DriveClientError, SyncError, MetadataError) as e:
        print(f"\n❌ Sync Error:")
        print(f"   {e}")
        return 1

    except KeyboardInterrupt:
        print("\n\n⚠️  Sync interrupted by user")
        print(f"   Partial progress has been saved")
        # Try to save metadata even on interrupt
        try:
            metadata.save()
        except:
            pass
        return 130

    except Exception as e:
        print(f"\n❌ Unexpected Error:")
        print(f"   {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

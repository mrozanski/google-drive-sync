#!/usr/bin/env python3
"""Google Drive to iCloud Sync - Phase 1: Simple Download Tool

This tool downloads a Google Drive folder and converts files:
- Google Docs → Markdown (.md)
- Google Sheets → CSV (.csv)
- Other files are skipped (Phase 1 limitation)

This is a simple download tool without sync logic. Run it to download
the entire folder structure. In Phase 2, we'll add incremental sync.
"""

import sys
from pathlib import Path

from config import load_config, ConfigError
from auth import get_drive_service, AuthenticationError
from drive_client import DriveClient, DriveClientError
from downloader import Downloader, DownloadError


def main():
    """Main entry point for the download tool."""
    print("=" * 60)
    print("Google Drive Folder Download Tool - Phase 1")
    print("=" * 60)

    try:
        # Load configuration
        print("\n📋 Loading configuration...")
        config = load_config()
        print(f"   Source folder ID: {config.google_folder_id}")
        print(f"   Target directory: {config.target_directory}")

        # Authenticate with Google Drive
        print("\n🔐 Authenticating with Google Drive...")
        service = get_drive_service(config.credentials_file, config.token_file)
        print("   ✓ Authentication successful")

        # Create Drive client
        drive_client = DriveClient(service)

        # Create downloader
        downloader = Downloader(drive_client, config.target_directory)

        # Download folder
        print("\n⬇️  Starting download...")
        print(f"   Note: Only Google Docs and Sheets will be downloaded")
        print(f"   Other file types will be skipped in this version\n")

        downloader.download_folder(config.google_folder_id)

        # Print summary
        downloader.print_summary()

        print("\n✨ Download complete!")
        print(f"\nFiles saved to: {config.target_directory}")

        return 0

    except ConfigError as e:
        print(f"\n❌ Configuration Error:")
        print(f"   {e}")
        print(f"\nPlease create a .env file based on .env.example")
        return 1

    except AuthenticationError as e:
        print(f"\n❌ Authentication Error:")
        print(f"   {e}")
        return 1

    except (DriveClientError, DownloadError) as e:
        print(f"\n❌ Download Error:")
        print(f"   {e}")
        return 1

    except KeyboardInterrupt:
        print("\n\n⚠️  Download interrupted by user")
        return 130

    except Exception as e:
        print(f"\n❌ Unexpected Error:")
        print(f"   {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

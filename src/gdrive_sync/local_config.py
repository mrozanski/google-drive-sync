"""Local configuration discovery for synced folders.

A folder is considered initialized if it contains .gdrive-sync/metadata.json.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from gdrive_sync.metadata import Metadata


class LocalConfig:
    """Represents local sync configuration rooted at a directory."""

    def __init__(self, root: Path):
        self.root = root
        self.sync_dir = root / ".gdrive-sync"
        self.metadata_path = self.sync_dir / "metadata.json"

    @property
    def is_initialized(self) -> bool:
        return self.metadata_path.exists()

    def load_metadata(self) -> Metadata:
        return Metadata(self.root)


def find_local_root(start: Optional[Path] = None) -> Optional[LocalConfig]:
    """Search upwards from start (or cwd) for a synced folder."""
    current = (start or Path.cwd()).resolve()
    for path in [current, *current.parents]:
        config = LocalConfig(path)
        if config.is_initialized:
            return config
    return None

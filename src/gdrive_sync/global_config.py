"""Global configuration stored in ~/.config/gdrive-sync.

This module manages credential and token paths used across the CLI.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Dict, Optional

CONFIG_DIR = Path.home() / ".config" / "gdrive-sync"


class GlobalConfigError(Exception):
    """Raised when global configuration is missing or invalid."""


class GlobalConfig:
    """Represents global configuration stored under ~/.config/gdrive-sync."""

    def __init__(self) -> None:
        self.config_dir = CONFIG_DIR
        self.credentials_path = self.config_dir / "credentials.json"
        self.token_path = self.config_dir / "token.json"
        self.settings_path = self.config_dir / "config.json"
        self.config_dir.mkdir(parents=True, exist_ok=True)

    def has_credentials(self) -> bool:
        return self.credentials_path.exists()

    def has_token(self) -> bool:
        return self.token_path.exists()

    def install_credentials(self, source: Path) -> None:
        """Copy provided credentials file into the global config directory."""
        if not source.exists():
            raise GlobalConfigError(f"Credentials file not found at {source}")
        self.credentials_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(source, self.credentials_path)

    def clear_token(self) -> None:
        """Remove cached OAuth token (forces re-auth)."""
        if self.token_path.exists():
            self.token_path.unlink()

    def load_settings(self) -> Dict[str, Any]:
        if not self.settings_path.exists():
            return {}
        with open(self.settings_path, "r") as f:
            return json.load(f)

    def save_settings(self, data: Dict[str, Any]) -> None:
        self.settings_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.settings_path, "w") as f:
            json.dump(data, f, indent=2)

    def get_setting(self, key: str, default: Optional[Any] = None) -> Any:
        return self.load_settings().get(key, default)

    def set_setting(self, key: str, value: Any) -> None:
        settings = self.load_settings()
        settings[key] = value
        self.save_settings(settings)

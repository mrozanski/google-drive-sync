"""Configuration management for Google Drive sync."""

import os
from pathlib import Path
from dotenv import load_dotenv


class ConfigError(Exception):
    """Raised when configuration is missing or invalid."""
    pass


class Config:
    """Manages application configuration from .env file."""

    def __init__(self):
        """Load and validate configuration."""
        # Load .env file
        load_dotenv()

        # Validate and load required configuration
        self.google_folder_id = self._get_required("GOOGLE_FOLDER_ID")
        self.target_directory = self._get_required_path("TARGET_DIRECTORY")
        self.credentials_file = self._get_required_path("GOOGLE_CREDENTIALS_FILE")

        # Optional configuration with defaults
        self.token_file = os.getenv("TOKEN_FILE", "token.json")

    def _get_required(self, key: str) -> str:
        """Get required environment variable or raise error."""
        value = os.getenv(key)
        if not value:
            raise ConfigError(
                f"Configuration missing: '{key}' not found in .env file. "
                f"Please check your .env file and ensure '{key}' is set."
            )
        return value

    def _get_required_path(self, key: str) -> Path:
        """Get required path environment variable and validate it exists (except target dir)."""
        value = self._get_required(key)
        path = Path(value).expanduser()

        # For credentials file, check it exists
        if key == "GOOGLE_CREDENTIALS_FILE" and not path.exists():
            raise ConfigError(
                f"Configuration error: '{key}' points to '{value}' which does not exist. "
                f"Please ensure the file exists or update the path in .env file."
            )

        # For target directory, create if it doesn't exist
        if key == "TARGET_DIRECTORY":
            path.mkdir(parents=True, exist_ok=True)

        return path


def load_config() -> Config:
    """Load and validate configuration.

    Returns:
        Config: Validated configuration object

    Raises:
        ConfigError: If configuration is missing or invalid
    """
    env_file = Path(".env")
    if not env_file.exists():
        raise ConfigError(
            "Configuration missing: .env file not found in current directory. "
            "Please create a .env file based on .env.example"
        )

    return Config()

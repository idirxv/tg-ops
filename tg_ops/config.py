"""Configuration management for the application."""

import logging
import tomllib
from dataclasses import dataclass, field
from importlib.resources import files
from pathlib import Path
from typing import Dict, List

logger = logging.getLogger(__name__)

# --- Defaults ---
DEFAULT_PORT = 5000
DEFAULT_LOG_LEVEL = "INFO"


class ConfigError(Exception):
    """Base exception for configuration errors."""

    pass


@dataclass
class Config:
    """Application configuration."""

    bot_token: str
    webhook_url: str | None = None
    port: int = DEFAULT_PORT
    log_level: str = DEFAULT_LOG_LEVEL
    secret_token: str | None = None
    admin_id: int | None = None

    # Defaults are now empty lists/dicts, not hardcoded values
    monitored_services: List[str] = field(default_factory=list)
    monitored_disks: List[str] = field(default_factory=list)
    monitored_containers: Dict[str, str] = field(default_factory=dict)

    _file_path: Path | None = field(default=None, repr=False)

    @classmethod
    def load(cls, config_path: Path) -> "Config":
        """Load configuration from the specified path."""
        if not config_path.exists():
            cls._create_sample(config_path)
            raise ConfigError(f"Config file not found, creating sample at: {config_path}")

        try:
            with config_path.open("rb") as f:
                data = tomllib.load(f)
        except tomllib.TOMLDecodeError as e:
            raise ConfigError(f"Invalid TOML in {config_path}: {e}")

        # specific check for bot_token as it is mandatory
        if not data.get("bot_token"):
            raise ConfigError(f"Missing required field 'bot_token' in {config_path}")

        if not data.get("webhook_url"):
            raise ConfigError(f"Missing required field 'webhook_url' in {config_path}")

        # --- Validation Helpers ---
        def get_list_str(key: str) -> List[str]:
            """Safely retrieve a list of strings, defaulting to empty list if missing."""
            val = data.get(key, [])
            if not isinstance(val, list):
                raise ConfigError(f"Key '{key}' must be a list, got {type(val).__name__}")
            if val and not all(isinstance(x, str) for x in val):
                raise ConfigError(f"Key '{key}' must be a list of strings")
            return val

        def get_dict_str_str(key: str) -> Dict[str, str]:
            """Safely retrieve a dict of str:str, defaulting to empty dict if missing."""
            val = data.get(key, {})
            if not isinstance(val, dict):
                raise ConfigError(f"Key '{key}' must be a dictionary (TOML table)")
            for k, v in val.items():
                if not isinstance(k, str) or not isinstance(v, str):
                    raise ConfigError(f"Key '{key}': keys and values must be strings")
            return val

        def get_optional_str(key: str) -> str | None:
            val = data.get(key)
            if val is not None and not isinstance(val, str):
                raise ConfigError(f"Key '{key}' must be a string")
            return val or None  # Return None if string is empty

        def get_optional_int(key: str) -> int | None:
            val = data.get(key)
            if val is None:
                return None
            if not isinstance(val, int):
                raise ConfigError(f"Key '{key}' must be an integer")
            return val

        try:
            return cls(
                bot_token=str(data["bot_token"]),
                webhook_url=str(data.get("webhook_url")),
                port=int(data.get("port", DEFAULT_PORT)),
                log_level=str(data.get("log_level", DEFAULT_LOG_LEVEL)),
                secret_token=get_optional_str("secret_token"),
                admin_id=get_optional_int("admin_id"),
                monitored_services=get_list_str("monitored_services"),
                monitored_disks=get_list_str("monitored_disks"),
                monitored_containers=get_dict_str_str("monitored_containers"),
                _file_path=config_path,
            )
        except (ValueError, TypeError) as e:
            raise ConfigError(f"Configuration type error: {e}")

    @staticmethod
    def _create_sample(path: Path) -> None:
        """Create a sample configuration file with empty fields."""
        try:
            template = files("tg_ops.templates").joinpath("config.toml").read_text(encoding="utf-8")
            with path.open("w", encoding="utf-8") as f:
                f.write(template)
            # Set restrictive permissions (owner read/write only)
            try:
                path.chmod(0o600)
            except OSError:
                pass
        except OSError as e:
            raise ConfigError(f"Failed to create sample config at {path}: {e}")

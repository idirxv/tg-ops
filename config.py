from dataclasses import dataclass
import os
from typing import Optional

import yaml


@dataclass(frozen=True)
class Config:
    """Application configuration loaded from environment variables or YAML."""

    bot_token: str
    webhook_url: Optional[str]
    port: int = 5000
    secret_token: Optional[str] = None
    log_level: str = "INFO"

    @classmethod
    def load(cls, config_file: str = "config.yaml") -> "Config":
        """Create a configuration instance from a YAML file and env vars."""
        if not os.path.exists(config_file):
            raise FileNotFoundError(f"Configuration file not found: {config_file}")

        with open(config_file, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}

        bot_token = os.getenv("BOT_TOKEN", config.get("bot_token"))
        webhook_url = os.getenv("WEBHOOK_URL", config.get("webhook_url"))
        port = int(os.getenv("PORT", config.get("port", 5000)))
        # Optional secret token used to validate incoming webhook requests and to
        # register the webhook with Telegram. If not provided, the server will
        # not enforce header validation.
        secret_token = os.getenv("SECRET_TOKEN", config.get("secret_token"))
        # Optional log level (e.g., DEBUG, INFO, WARNING, ERROR)
        log_level = str(
            os.getenv("LOG_LEVEL", config.get("log_level", "INFO"))
        ).upper()

        if not bot_token:
            raise ValueError("bot_token must be provided in the configuration")

        return cls(
            bot_token=bot_token,
            webhook_url=webhook_url,
            port=port,
            secret_token=secret_token,
            log_level=log_level,
        )

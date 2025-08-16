import os
import yaml

class Config:
    """Configuration class for the application."""
    def __init__(self, config_file="config.yaml"):
        if not os.path.exists(config_file):
            raise FileNotFoundError(f"Configuration file not found: {config_file}")

        with open(config_file, "r") as f:
            config = yaml.safe_load(f) or {}

        self.bot_token = os.getenv("BOT_TOKEN", config.get("bot_token"))
        self.webhook_url = os.getenv("WEBHOOK_URL", config.get("webhook_url"))
        self.port = int(os.getenv("PORT", config.get("port", 5000)))
        # Optional secret token used to validate incoming webhook requests and to
        # register the webhook with Telegram. If not provided, the server will
        # not enforce header validation.
        self.secret_token = os.getenv("SECRET_TOKEN", config.get("secret_token"))
        # Optional log level (e.g., DEBUG, INFO, WARNING, ERROR)
        self.log_level = str(os.getenv("LOG_LEVEL", config.get("log_level", "INFO"))).upper()

        if not self.bot_token:
            raise ValueError("bot_token must be provided in the configuration")

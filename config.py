import os
import yaml

class Config:
    """Configuration class for the application."""
    def __init__(self, config_file="config.yaml"):
        if not os.path.exists(config_file):
            raise FileNotFoundError(f"Configuration file not found: {config_file}")

        with open(config_file, "r") as f:
            config = yaml.safe_load(f) or {}

        self.bot_token = config.get("bot_token")
        self.webhook_url = config.get("webhook_url")
        self.port = int(config.get("port", 5000))

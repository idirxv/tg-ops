"""Utility functions for managing Telegram webhooks via CLI."""

import logging

from telegram import Bot, WebhookInfo
from telegram.error import TelegramError


class WebhookManager:
    """Utility functions for managing Telegram webhooks via CLI."""

    def __init__(self, token: str, webhook_url: str | None, secret_token: str | None = None):
        self.bot = Bot(token=token)
        self.webhook_url = webhook_url
        self.secret_token = secret_token
        self.logger = logging.getLogger(self.__class__.__name__)

    async def set_webhook(self) -> bool:
        """Configure the webhook."""
        if not self.webhook_url:
            self.logger.error("Webhook URL is not configured")
            return False

        try:
            success = await self.bot.set_webhook(
                url=self.webhook_url,
                drop_pending_updates=True,
                secret_token=self.secret_token,
            )
            if success:
                self.logger.info("Webhook configured at %s", self.webhook_url)
            else:
                self.logger.warning("Failed to configure webhook.")
            return success
        except TelegramError as e:
            self.logger.error("Error during set_webhook: %s", e)
            return False

    async def unset_webhook(self) -> bool:
        """Delete the current webhook."""
        try:
            success = await self.bot.delete_webhook()
            if success:
                self.logger.info("Webhook deleted successfully.")
            else:
                self.logger.warning("Failed to delete webhook.")
            return success
        except TelegramError as e:
            self.logger.error("Error during unset_webhook: %s", e)
            return False

    async def get_webhook_info(self) -> WebhookInfo | None:
        """Get the current webhook info."""
        try:
            info = await self.bot.get_webhook_info()
            self.logger.info("Webhook info: %s", info.to_dict())
            return info
        except TelegramError as e:
            self.logger.error("Error during get_webhook_info: %s", e)
            return None

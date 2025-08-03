"""Utility functions for managing Telegram webhooks via CLI."""

from __future__ import annotations

import logging
from telegram import Bot
from config import Config

log = logging.getLogger(__name__)


async def manage(set_: bool, *, cfg: Config) -> None:
    """Register or delete the webhook."""
    async with Bot(cfg.bot_token) as bot:
        if set_:
            await bot.set_webhook(f"{cfg.webhook_url}/webhook")
            log.info("Webhook registered → %s/webhook", cfg.webhook_url)
        else:
            await bot.delete_webhook()
            log.info("Webhook deleted")

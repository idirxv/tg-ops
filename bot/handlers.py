"""Group all Telegram handlers (commands, callbacks, etc.)."""

from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, Application


async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reply with 'pong' – perfect for testing the bot's health."""
    await update.message.reply_text("pong")


def register(application: Application) -> None:
    """Register all handlers on the given application instance."""
    application.add_handler(CommandHandler("ping", ping))

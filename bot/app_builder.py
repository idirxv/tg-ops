"""Application builder and lifecycle management."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator, Final

from telegram.ext import ApplicationBuilder, Application

from bot.handlers import register as register_handlers
from config import Config

log = logging.getLogger(__name__)


async def _build(config: Config) -> Application:
    app = ApplicationBuilder().token(config.bot_token).build()
    register_handlers(app)

    await app.initialize()
    await app.start()

    me = await app.bot.get_me()
    log.info("Telegram bot connected - @%s", me.username)
    return app


@asynccontextmanager
async def lifespan(config: Config) -> AsyncIterator[Application]:
    """Properly manage the application's startup and shutdown."""
    application: Final = await _build(config)
    try:
        yield application
    finally:
        log.info("Stopping the bot...")
        await application.stop()
        await application.shutdown()

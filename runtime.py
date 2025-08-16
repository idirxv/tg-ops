"""Run the Telegram bot and HTTP webhook server concurrently."""
from __future__ import annotations

import asyncio
import logging
import signal
from contextlib import suppress
from types import FrameType
from typing import Final

from bot.app_builder import lifespan as bot_lifespan
from config import Config
from web.server import create_server, WebServer

log = logging.getLogger(__name__)

__all__ = ["run"]


async def run(cfg: Config) -> None:
    """Start the bot and the webhook http server, then wait for shutdown."""
    loop: Final = asyncio.get_running_loop()

    async with bot_lifespan(cfg) as application:
        server: WebServer = create_server(
            application,
            loop=loop,
            host="0.0.0.0",
            port=cfg.port,
            secret_token=getattr(cfg, "secret_token", None),
        )
        # Run the HTTP server in its own daemon thread
        server.start()

        stop_event = asyncio.Event()

        def _stop(*_: object, **__: FrameType | None) -> None:  # noqa: D401
            """Signal handler that triggers an orderly shutdown."""
            stop_event.set()

        for sig in (signal.SIGINT, signal.SIGTERM):
            with suppress(NotImplementedError):  # Windows compatibility
                loop.add_signal_handler(sig, _stop)

        log.info("PiCommander is running on port %s", cfg.port)
        await stop_event.wait()

        # If we reach this point, a shutdown signal was received – stop HTTP server.
        server.stop()

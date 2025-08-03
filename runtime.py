"""Run the Telegram bot and Flask webhook server concurrently."""
from __future__ import annotations

import asyncio
import logging
import signal
from contextlib import suppress
from types import FrameType
from typing import Final

from bot.app_builder import lifespan as bot_lifespan
from config import Config
from web.server import create_server, serve

log = logging.getLogger(__name__)

__all__ = ["run"]


async def run(cfg: Config) -> None:
    """Start the bot and the webhook http server, then wait for shutdown."""
    loop: Final = asyncio.get_running_loop()

    async with bot_lifespan(cfg) as application:
        flask_app = create_server(application, loop=loop)

        flask_task = asyncio.create_task(
            asyncio.to_thread(serve, flask_app, host="0.0.0.0", port=cfg.port)
        )

        stop_event = asyncio.Event()

        def _stop(*_: object, **__: FrameType | None) -> None:  # noqa: D401
            """Signal handler that triggers an orderly shutdown."""
            stop_event.set()

        for sig in (signal.SIGINT, signal.SIGTERM):
            with suppress(NotImplementedError):  # Windows compatibility
                loop.add_signal_handler(sig, _stop)

        log.info("PiCommander is running on port %s", cfg.port)
        await stop_event.wait()

        # If we reach this point, a shutdown signal was received – let the
        # server finish its current requests (best-effort) and cancel
        # background task if it's still running.
        if not flask_task.done():
            flask_task.cancel()
            with suppress(asyncio.CancelledError):
                await flask_task

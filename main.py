"""Entry point of the application."""

from __future__ import annotations

import argparse
import asyncio
import logging
import signal
from threading import Thread

from telegram import Bot

from bot.app_builder import lifespan as bot_lifespan
from config import Config
from logging_setup import setup_logging
from web.server import create_server


def _serve_flask(app, *, host: str, port: int) -> None:
    """Launch Flask in a dedicated thread to leave the asyncio loop free."""
    app.run(host=host, port=port, threaded=True, use_reloader=False)


async def _webhook_cli(set_: bool, *, cfg: Config) -> None:
    """CLI utility – register or remove the webhook from Telegram."""
    async with Bot(cfg.bot_token) as bot:
        if set_:
            await bot.set_webhook(f"{cfg.webhook_url}/webhook")
            logging.info("✅ Webhook registered → %s/webhook", cfg.webhook_url)
        else:
            await bot.delete_webhook()
            logging.info("🗑️  Webhook deleted")


def main() -> None:  # pragma: no cover
    """Main entry point."""
    setup_logging()
    cfg = Config()

    parser = argparse.ArgumentParser("PiCommander")
    parser.add_argument("--set-webhook", action="store_true")
    parser.add_argument("--delete-webhook", action="store_true")
    args = parser.parse_args()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    if args.set_webhook or args.delete_webhook:
        loop.run_until_complete(_webhook_cli(set_=args.set_webhook, cfg=cfg))
        return

    async def runner() -> None:  # noqa: WPS430
        async with bot_lifespan(cfg) as application:
            flask_app = create_server(application, loop=loop)
            Thread(
                target=_serve_flask,
                daemon=True,
                args=(flask_app,),
                kwargs={"host": "0.0.0.0", "port": cfg.port},
            ).start()

            stop_event = asyncio.Event()

            def _stop(*_: object) -> None:
                stop_event.set()

            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(sig, _stop)

            logging.info("🚀 PiCommander is running on port %s", cfg.port)
            await stop_event.wait()

    loop.run_until_complete(runner())


if __name__ == "__main__":  # pragma: no cover
    main()

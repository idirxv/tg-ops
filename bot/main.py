"""Entrypoint: python -m bot.main"""
from __future__ import annotations

import logging
import sys
from typing import Any

from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    TypeHandler,
)

from bot.auth import make_auth_gate
from bot.config import Config, ConfigError
from bot.dockhand import DockhandClient
from bot.handlers import cmd_docker, cmd_ping, on_callback, on_error

log = logging.getLogger(__name__)


def build_application(config: Config, client: DockhandClient) -> Application:
    app = Application.builder().token(config.telegram_bot_token).build()
    app.bot_data["config"] = config
    app.bot_data["client"] = client
    # Group -1 runs before all default-group handlers, for every update type.
    app.add_handler(
        TypeHandler(Update, make_auth_gate(config.allowed_chat_ids)), group=-1
    )
    app.add_handler(CommandHandler("ping", cmd_ping))
    app.add_handler(CommandHandler("docker", cmd_docker))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_error_handler(on_error)
    return app


def main() -> int:
    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s %(message)s", level=logging.INFO
    )
    # PTB's httpx transport is chatty at INFO
    logging.getLogger("httpx").setLevel(logging.WARNING)

    try:
        config = Config.from_env()
    except ConfigError as exc:
        log.error("Configuration error: %s", exc)
        return 1

    logging.getLogger().setLevel(config.log_level)
    client = DockhandClient(
        config.dockhand_url, config.dockhand_api_token, config.dockhand_env
    )
    app = build_application(config, client)
    log.info(
        "Bot starting: %d allowed chat(s), stacks: %s",
        len(config.allowed_chat_ids),
        ", ".join(config.allowed_stacks),
    )
    run_kwargs: dict[str, Any] = {
        "allowed_updates": [Update.MESSAGE, Update.CALLBACK_QUERY],
        "drop_pending_updates": True,
    }
    if config.webhook is None:
        app.run_polling(**run_kwargs)
    else:
        log.info("Webhook mode: listening on :%d", config.webhook.port)
        app.run_webhook(
            listen="0.0.0.0",
            port=config.webhook.port,
            url_path=config.webhook.path,
            webhook_url=config.webhook.url,
            secret_token=config.webhook.secret,
            **run_kwargs,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())

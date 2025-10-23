"""Application builder and lifecycle management."""

from telegram.ext import Application, ApplicationBuilder

from tg_ops.bot.handlers import register_handlers
from tg_ops.config import Config


def build_app(cfg: Config) -> Application:
    """Build and return a Telegram bot application."""
    app = ApplicationBuilder().token(cfg.bot_token).build()
    register_handlers(app, cfg)
    return app


def run_server(cfg: Config) -> None:
    """Run the webhook server."""

    application = build_app(cfg)

    webhook_path = "webhook"

    # Run until interrupted, handle lifecycle internally.
    application.run_webhook(
        listen="0.0.0.0",
        port=cfg.port,
        url_path=webhook_path,
        webhook_url=f"{cfg.webhook_url}/{webhook_path}",
        secret_token=cfg.secret_token or None,
        drop_pending_updates=True,
    )

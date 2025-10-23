"""Command-line interface for tg-ops."""

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from typing import Sequence

from tg_ops.bot.app_runner import run_server
from tg_ops.bot.webhook import WebhookManager
from tg_ops.config import Config, ConfigError

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    """Construct the top-level argument parser."""
    parser = argparse.ArgumentParser(prog="tg-ops", description="Telegram Operations Bot")

    # Global argument for config file
    parser.add_argument(
        "-f",
        "--file",
        type=Path,
        default=Path.home() / ".tg-ops.toml",
        help="Path to the configuration file (default: ~/.tg-ops.toml)",
    )

    sub = parser.add_subparsers(dest="command", help="Command to execute")

    # --- run ---
    sub.add_parser("run", help="Start the bot and HTTP server")

    # --- webhook ---
    webhook = sub.add_parser("webhook", help="Manage Telegram webhooks")
    webhook_sub = webhook.add_subparsers(dest="action", required=True)

    webhook_sub.add_parser("set", help="Register the webhook")
    webhook_sub.add_parser("get", help="Get current webhook info")
    webhook_sub.add_parser("unset", help="Delete the webhook")

    return parser


def main(argv: Sequence[str] | None = None) -> None:
    """Main entry point."""

    parser = build_parser()
    args = parser.parse_args(argv)

    # Default command is 'run' if none specified
    if args.command is None:
        args.command = "run"

    # Load configuration
    try:
        cfg = Config.load(args.file)
    except ConfigError as e:
        logger.error("Failed to load configuration: %s", e)
        sys.exit(1)

    logging.basicConfig(level=cfg.log_level, format="%(levelname)s - %(message)s")

    try:
        if args.command == "run":
            logger.info("Starting application with config: %s", args.file)
            run_server(cfg)

        elif args.command == "webhook":

            async def do_webhook():
                manager = WebhookManager(cfg.bot_token, cfg.webhook_url, cfg.secret_token)
                if args.action == "set":
                    if not cfg.webhook_url:
                        logger.error("Webhook URL is missing in config.")
                        return
                    await manager.set_webhook()
                elif args.action == "get":
                    await manager.get_webhook_info()
                elif args.action == "unset":
                    await manager.unset_webhook()

            asyncio.run(do_webhook())

    except Exception as e:
        logger.exception("An unexpected error occurred: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()

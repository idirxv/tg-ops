"""Entry point of the application."""

from __future__ import annotations

import argparse
import asyncio
from bot.webhook import manage as webhook_cli
from runtime import run as run_services
from config import Config
from logging_setup import setup_logging


def main() -> None:
    """Main entry point."""
    cfg = Config()
    setup_logging(cfg.log_level)

    parser = argparse.ArgumentParser("PiCommander")
    parser.add_argument("--set-webhook", action="store_true")
    parser.add_argument("--delete-webhook", action="store_true")
    args = parser.parse_args()

    if args.set_webhook or args.delete_webhook:
        asyncio.run(webhook_cli(set_=args.set_webhook, cfg=cfg))
        return

    asyncio.run(run_services(cfg))


if __name__ == "__main__":
    main()

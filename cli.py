"""Command-line interface for PiCommander."""

from __future__ import annotations

import argparse
import asyncio
from typing import Sequence

from bot.webhook import manage as manage_webhook
from config import Config
from logging_setup import setup_logging
from runtime import run as run_services


def build_parser() -> argparse.ArgumentParser:
    """Construct the top-level argument parser."""
    parser = argparse.ArgumentParser("PiCommander")
    sub = parser.add_subparsers(dest="command")
    sub.required = False

    sub.add_parser("run", help="Start the bot and HTTP server (default)")

    webhook = sub.add_parser("webhook", help="Manage Telegram webhooks")
    action = webhook.add_subparsers(dest="action", required=True)
    action.add_parser("set", help="Register the webhook")
    action.add_parser("delete", help="Delete the webhook")

    return parser


def main(argv: Sequence[str] | None = None) -> None:
    """Parse CLI arguments and dispatch to commands."""
    cfg = Config.load()
    setup_logging(cfg.log_level)

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "webhook":
        asyncio.run(manage_webhook(set_=(args.action == "set"), cfg=cfg))
    else:
        asyncio.run(run_services(cfg))


__all__ = ["main", "build_parser"]

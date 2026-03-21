"""Command-line interface for tg-ops."""

import asyncio
import logging
from pathlib import Path
from typing import Annotated

import typer

from tg_ops.bot.app_runner import run_server
from tg_ops.bot.webhook import WebhookManager
from tg_ops.config import Config, ConfigError

logger = logging.getLogger(__name__)

app = typer.Typer(
    name="tg-ops", help="Telegram Operations Bot", no_args_is_help=True, add_completion=False
)
webhook_app = typer.Typer(help="Manage Telegram webhooks")
app.add_typer(webhook_app, name="webhook")

CONFIG_OPTION = Annotated[
    Path,
    typer.Option("-f", "--file", help="Path to the configuration file (default: ~/.tg-ops.toml)"),
]


def _load_config(file: Path) -> Config:
    try:
        return Config.load(file)
    except ConfigError as e:
        typer.echo(f"Error: Failed to load configuration: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def run(
    file: CONFIG_OPTION = Path.home() / ".tg-ops.toml",
) -> None:
    """Start the bot and HTTP server."""
    cfg = _load_config(file)
    logging.basicConfig(level=cfg.log_level, format="%(levelname)s - %(message)s")
    logger.info("Starting application with config: %s", file)
    run_server(cfg)


@webhook_app.command("set")
def webhook_set(
    file: CONFIG_OPTION = Path.home() / ".tg-ops.toml",
) -> None:
    """Register the webhook with Telegram."""
    cfg = _load_config(file)
    logging.basicConfig(level=cfg.log_level, format="%(levelname)s - %(message)s")

    if not cfg.webhook_url:
        typer.echo("Error: Webhook URL is missing in config.", err=True)
        raise typer.Exit(1)

    async def _set():
        manager = WebhookManager(cfg.bot_token, cfg.webhook_url, cfg.secret_token)
        ok = await manager.set_webhook()
        if ok:
            typer.echo(f"Webhook registered: {cfg.webhook_url}/webhook")
        else:
            typer.echo("Failed to register webhook.", err=True)
            raise typer.Exit(1)

    asyncio.run(_set())


@webhook_app.command("get")
def webhook_get(
    file: CONFIG_OPTION = Path.home() / ".tg-ops.toml",
) -> None:
    """Get current webhook info."""
    cfg = _load_config(file)
    logging.basicConfig(level=cfg.log_level, format="%(levelname)s - %(message)s")

    async def _get():
        manager = WebhookManager(cfg.bot_token, cfg.webhook_url, cfg.secret_token)
        info = await manager.get_webhook_info()
        if info:
            typer.echo(info.to_dict())
        else:
            typer.echo("Failed to retrieve webhook info.", err=True)
            raise typer.Exit(1)

    asyncio.run(_get())


@webhook_app.command("unset")
def webhook_unset(
    file: CONFIG_OPTION = Path.home() / ".tg-ops.toml",
) -> None:
    """Delete the webhook."""
    cfg = _load_config(file)
    logging.basicConfig(level=cfg.log_level, format="%(levelname)s - %(message)s")

    async def _unset():
        manager = WebhookManager(cfg.bot_token, cfg.webhook_url, cfg.secret_token)
        ok = await manager.unset_webhook()
        if ok:
            typer.echo("Webhook deleted.")
        else:
            typer.echo("Failed to delete webhook.", err=True)
            raise typer.Exit(1)

    asyncio.run(_unset())


def main() -> None:
    app()


if __name__ == "__main__":
    main()

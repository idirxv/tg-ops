"""Environment-variable configuration for the bot."""
from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import urlsplit

# Telegram callback_data is capped at 64 bytes; longest action prefix is
# "restart|" (8 bytes), so stack names must fit in the remainder.
_MAX_STACK_NAME_BYTES = 55

_REQUIRED = (
    "TELEGRAM_BOT_TOKEN",
    "DOCKHAND_URL",
    "DOCKHAND_API_TOKEN",
    "ALLOWED_CHAT_IDS",
    "ALLOWED_STACKS",
    # Dockhand scopes /api/stacks by ?env=<environment id>; without it the
    # API answers 200 with an empty list, which looks like "no stacks".
    "DOCKHAND_ENV",
)

# Telegram's constraint on setWebhook secret_token
_SECRET_RE = re.compile(r"^[A-Za-z0-9_-]{1,256}$")


class ConfigError(ValueError):
    """Invalid or missing configuration."""


class BotMode(StrEnum):
    POLLING = "polling"
    WEBHOOK = "webhook"


@dataclass(frozen=True)
class Webhook:
    """Built only for BOT_MODE=webhook, so url and secret are always set."""

    url: str
    secret: str
    port: int = 5555

    @property
    def path(self) -> str:
        return urlsplit(self.url).path.lstrip("/")


@dataclass(frozen=True)
class Config:
    telegram_bot_token: str
    dockhand_url: str
    dockhand_api_token: str
    allowed_chat_ids: frozenset[int]
    allowed_stacks: tuple[str, ...]
    dockhand_env: str
    log_level: str
    # None selects polling mode; a Webhook selects webhook mode.
    webhook: Webhook | None = None

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Config:
        if env is None:
            env = os.environ

        missing = [name for name in _REQUIRED if not env.get(name, "").strip()]
        if missing:
            raise ConfigError(
                "missing required environment variables: " + ", ".join(missing)
            )

        return cls(
            telegram_bot_token=env["TELEGRAM_BOT_TOKEN"].strip(),
            dockhand_url=env["DOCKHAND_URL"].strip().rstrip("/"),
            dockhand_api_token=env["DOCKHAND_API_TOKEN"].strip(),
            allowed_chat_ids=_parse_chat_ids(env["ALLOWED_CHAT_IDS"]),
            allowed_stacks=_parse_stacks(env["ALLOWED_STACKS"]),
            dockhand_env=_parse_dockhand_env(env["DOCKHAND_ENV"]),
            log_level=env.get("LOG_LEVEL", "").strip().upper() or "INFO",
            webhook=_parse_webhook(env),
        )


def _split(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def _parse_chat_ids(raw: str) -> frozenset[int]:
    try:
        return frozenset(int(part) for part in _split(raw))
    except ValueError as exc:
        raise ConfigError("ALLOWED_CHAT_IDS must be comma-separated integers") from exc


def _parse_stacks(raw: str) -> tuple[str, ...]:
    stacks = tuple(dict.fromkeys(_split(raw)))
    for name in stacks:
        if "|" in name:
            raise ConfigError(f"stack name may not contain '|': {name!r}")
        if len(name.encode()) > _MAX_STACK_NAME_BYTES:
            raise ConfigError(
                f"stack name too long (max {_MAX_STACK_NAME_BYTES} bytes): {name!r}"
            )
    return stacks


def _parse_dockhand_env(raw: str) -> str:
    value = raw.strip()
    if not value.isdigit():
        raise ConfigError(
            "DOCKHAND_ENV must be the numeric Dockhand environment id "
            f"(see GET /api/environments), got {value!r}"
        )
    return value


def _parse_webhook(env: Mapping[str, str]) -> Webhook | None:
    raw_mode = env.get("BOT_MODE", "").strip().lower() or BotMode.POLLING.value
    try:
        mode = BotMode(raw_mode)
    except ValueError as exc:
        modes = tuple(m.value for m in BotMode)
        raise ConfigError(f"BOT_MODE must be one of {modes}, got {raw_mode!r}") from exc
    if mode is BotMode.POLLING:
        return None

    url = env.get("WEBHOOK_URL", "").strip()
    if not url:
        raise ConfigError("WEBHOOK_URL is required when BOT_MODE=webhook")
    if not url.startswith("https://"):
        raise ConfigError("WEBHOOK_URL must use https://")

    secret = env.get("WEBHOOK_SECRET", "").strip()
    if not secret:
        raise ConfigError("WEBHOOK_SECRET is required when BOT_MODE=webhook")
    if not _SECRET_RE.match(secret):
        raise ConfigError("WEBHOOK_SECRET must be 1-256 chars of A-Za-z0-9_-")

    return Webhook(url=url, secret=secret, port=_parse_port(env))


def _parse_port(env: Mapping[str, str]) -> int:
    raw = env.get("WEBHOOK_PORT", "").strip() or "5555"
    try:
        port = int(raw)
    except ValueError as exc:
        raise ConfigError("WEBHOOK_PORT must be an integer") from exc
    if not 1 <= port <= 65535:
        raise ConfigError("WEBHOOK_PORT must be between 1 and 65535")
    return port

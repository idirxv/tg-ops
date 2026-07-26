import pytest

from bot.config import Config

# Minimal valid environment. The stray whitespace and the negative chat id
# are deliberate: they exercise the parsers' trimming and sign handling.
_BASE_ENV = {
    "TELEGRAM_BOT_TOKEN": "123:abc",
    "DOCKHAND_URL": "http://dockhand:3000/",
    "DOCKHAND_API_TOKEN": "dh_token",
    "ALLOWED_CHAT_IDS": "111, -222",
    "ALLOWED_STACKS": "media, vpn",
    "DOCKHAND_ENV": "1",
}

_WEBHOOK_OVERRIDES = {
    "BOT_MODE": "webhook",
    "WEBHOOK_URL": "https://tgbot.example.com/telegram",
    "WEBHOOK_SECRET": "s3cret_-token",
}


@pytest.fixture
def base_env() -> dict[str, str]:
    return dict(_BASE_ENV)


@pytest.fixture
def webhook_env() -> dict[str, str]:
    return _BASE_ENV | _WEBHOOK_OVERRIDES


@pytest.fixture
def config() -> Config:
    return Config.from_env(_BASE_ENV)

"""Tests for bot/webhook.py."""

from unittest.mock import AsyncMock

import pytest
from telegram.error import TelegramError

from tg_ops.bot.webhook import WebhookManager


@pytest.fixture
def mock_bot(mocker):
    bot = mocker.patch("tg_ops.bot.webhook.Bot").return_value
    bot.set_webhook = AsyncMock(return_value=True)
    bot.delete_webhook = AsyncMock(return_value=True)
    bot.get_webhook_info = AsyncMock(return_value=object())
    return bot


async def test_set_webhook_passes_secret_token(mock_bot):
    manager = WebhookManager("token", "https://example.com", secret_token="mysecret")
    await manager.set_webhook()
    mock_bot.set_webhook.assert_called_once_with(
        url="https://example.com",
        drop_pending_updates=True,
        secret_token="mysecret",
    )


@pytest.mark.parametrize(
    "method,setup",
    [
        ("set_webhook", lambda bot: setattr(bot, "set_webhook", AsyncMock(side_effect=TelegramError("err")))),
        ("unset_webhook", lambda bot: setattr(bot, "delete_webhook", AsyncMock(side_effect=TelegramError("err")))),
        ("get_webhook_info", lambda bot: setattr(bot, "get_webhook_info", AsyncMock(side_effect=TelegramError("err")))),
    ],
)
async def test_telegram_error_returns_falsy(mock_bot, method, setup):
    setup(mock_bot)
    manager = WebhookManager("token", "https://example.com")
    result = await getattr(manager, method)()
    assert not result

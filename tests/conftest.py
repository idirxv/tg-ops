"""Shared fixtures for the tg-ops test suite."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from tg_ops.bot.handlers import BotHandlers
from tg_ops.config import Config


@pytest.fixture
def base_config() -> Config:
    return Config(bot_token="test-token", webhook_url="https://example.com", admin_id=123)


def make_update(user_id: int, has_callback: bool = False) -> MagicMock:
    """Build a minimal mock Update."""
    update = MagicMock()
    update.effective_user.id = user_id
    update.effective_message.reply_text = AsyncMock()
    update.effective_message.reply_chat_action = AsyncMock()

    if has_callback:
        query = MagicMock()
        query.answer = AsyncMock()
        query.delete_message = AsyncMock()
        query.edit_message_text = AsyncMock()
        update.callback_query = query
    else:
        update.callback_query = None

    return update


@pytest.fixture
def mock_context() -> MagicMock:
    ctx = MagicMock()
    ctx.args = []
    return ctx


@pytest.fixture
def bot_handlers(base_config: Config, mocker) -> BotHandlers:
    mocker.patch("tg_ops.bot.commands.services.docker.from_env")
    return BotHandlers(base_config)

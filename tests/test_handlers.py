"""Tests for bot/handlers.py."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram.ext import ConversationHandler

from tests.conftest import make_update
from tg_ops.bot.handlers import WAITING_SHELL_CMD


# --- @restricted decorator ---


async def test_restricted_no_admin_id_blocks_all(bot_handlers, mock_context):
    bot_handlers.cfg.admin_id = None
    update = make_update(user_id=999)
    mock_execute = AsyncMock()
    bot_handlers.shell_service.execute = mock_execute

    await bot_handlers.uptime(update, mock_context)

    update.effective_message.reply_text.assert_called_once()
    msg = update.effective_message.reply_text.call_args[0][0]
    assert "not configured" in msg
    mock_execute.assert_not_called()


async def test_restricted_wrong_user_denied(bot_handlers, mock_context):
    bot_handlers.cfg.admin_id = 123
    update = make_update(user_id=999)

    await bot_handlers.uptime(update, mock_context)

    update.effective_message.reply_text.assert_called_once()
    msg = update.effective_message.reply_text.call_args[0][0]
    assert "Access denied" in msg


async def test_restricted_correct_user_handler_runs(bot_handlers, mock_context, mocker):
    bot_handlers.cfg.admin_id = 123
    update = make_update(user_id=123)
    bot_handlers.shell_service.execute = AsyncMock(return_value=(0, "up output", ""))

    await bot_handlers.uptime(update, mock_context)

    bot_handlers.shell_service.execute.assert_called_once_with("uptime")


# --- exec_entry conversation ---


async def test_exec_entry_with_args_executes_and_ends(bot_handlers, mock_context):
    bot_handlers.cfg.admin_id = 123
    update = make_update(user_id=123)
    mock_context.args = ["echo", "hi"]
    bot_handlers.shell_service.execute = AsyncMock(return_value=(0, "hi", ""))

    result = await bot_handlers.exec_entry(update, mock_context)

    assert result == ConversationHandler.END
    bot_handlers.shell_service.execute.assert_called_once_with("echo hi")
    assert update.effective_message.reply_text.call_count == 2


async def test_exec_entry_no_args_prompts_and_waits(bot_handlers, mock_context):
    bot_handlers.cfg.admin_id = 123
    update = make_update(user_id=123)
    mock_context.args = []

    result = await bot_handlers.exec_entry(update, mock_context)

    assert result == WAITING_SHELL_CMD
    update.effective_message.reply_text.assert_called_once()
    msg = update.effective_message.reply_text.call_args[0][0]
    assert "shell command" in msg.lower()


# --- button_handler callbacks ---


async def test_button_close_menu_deletes_message(bot_handlers, mock_context):
    bot_handlers.cfg.admin_id = 123
    update = make_update(user_id=123, has_callback=True)
    update.callback_query.data = "close_menu"

    await bot_handlers.button_handler(update, mock_context)

    update.callback_query.delete_message.assert_called_once()


async def test_button_docker_action_calls_perform_action(bot_handlers, mock_context, mocker):
    bot_handlers.cfg.admin_id = 123
    update = make_update(user_id=123, has_callback=True)
    update.callback_query.data = "docker_action:restart:mybox"

    mocker.patch.object(
        bot_handlers.docker_manager, "perform_action", new=AsyncMock(return_value=True)
    )
    mocker.patch.object(
        bot_handlers.docker_manager, "get_active_containers", new=AsyncMock(return_value=[])
    )

    await bot_handlers.button_handler(update, mock_context)

    bot_handlers.docker_manager.perform_action.assert_called_once_with("restart", "mybox")

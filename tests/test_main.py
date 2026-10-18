import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram import Update
from telegram.ext import CallbackQueryHandler, CommandHandler, TypeHandler
from telegram.ext._utils.webhookhandler import WebhookAppClass, WebhookServer
from tornado.httpserver import HTTPServer

from bot.main import WEBHOOK_MAX_BODY_BYTES, build_application, limit_webhook_body_size


def test_build_application_wires_everything(config):
    app = build_application(config, MagicMock())
    assert app.bot_data["config"] is config
    # auth gate runs first, in its own group before all others
    assert min(app.handlers) == -1
    assert isinstance(app.handlers[-1][0], TypeHandler)
    default_group = [type(h) for h in app.handlers[0]]
    assert CommandHandler in default_group
    assert CallbackQueryHandler in default_group


def test_start_command_lists_stacks(config):
    """Telegram clients send /start on first contact."""
    app = build_application(config, MagicMock())
    commands = set().union(
        *(h.commands for h in app.handlers[0] if isinstance(h, CommandHandler))
    )
    assert {"start", "docker", "ping"} <= commands


async def test_unauthorized_callback_never_reaches_handlers(config, monkeypatch):
    """End to end through PTB: the gate stops a forged callback from a chat
    outside the allowlist before any Dockhand call."""
    client = MagicMock()
    app = build_application(config, client)
    # Stub every Bot API call so that, without the gate, the handler would
    # get all the way to Dockhand instead of failing on the network first.
    stubbed = ("initialize", "shutdown", "answer_callback_query", "edit_message_text")
    for method in stubbed:
        monkeypatch.setattr(type(app.bot), method, AsyncMock())
    await app.initialize()
    update = Update.de_json(
        {
            "update_id": 1,
            "callback_query": {
                "id": "1",
                "chat_instance": "x",
                "data": "cstop|media",
                "from": {"id": 999, "is_bot": False, "first_name": "Eve"},
                "message": {
                    "message_id": 1,
                    "date": 0,
                    "chat": {"id": 999, "type": "private"},
                },
            },
        },
        app.bot,
    )
    await app.process_update(update)
    await app.shutdown()
    client.list_stacks.assert_not_called()
    client.stack_action.assert_not_called()


@pytest.fixture
def restore_httpserver_config():
    saved = HTTPServer._save_configuration()
    yield
    HTTPServer._restore_configuration(saved)


def test_webhook_server_body_size_is_capped(restore_httpserver_config):
    """Guards against PTB changing how it builds its tornado server."""
    limit_webhook_body_size()
    app = WebhookAppClass("/telegram", MagicMock(), asyncio.Queue(), "secret")
    server = WebhookServer("127.0.0.1", 0, app, None)
    assert server._http_server.conn_params.max_body_size == WEBHOOK_MAX_BODY_BYTES

from unittest.mock import AsyncMock, MagicMock

from bot.dockhand import DockhandError
from bot.handlers import on_callback, render_detail, render_list
from bot.stacks import Container, Stack, StackStatus


def _ctx(config, client):
    context = MagicMock()
    context.bot_data = {"config": config, "client": client}
    return context


def _update(callback_data):
    q = AsyncMock()
    q.data = callback_data
    update = MagicMock()
    update.callback_query = q
    update.effective_chat.id = 111
    return update, q


def test_render_list_empty():
    assert "No controllable stacks" in render_list([])


def test_render_detail_shows_status_and_containers():
    stack = Stack(
        "media",
        StackStatus.PARTIAL,
        (Container("media-app-1", "running"), Container("media-db-1", "exited")),
    )
    text = render_detail(stack)
    assert "🟡" in text
    assert "media-app-1" in text
    assert "exited" in text


def test_render_detail_escapes_html():
    stack = Stack("media", StackStatus.STOPPED, (Container("<b>x</b>", "exited"),))
    text = render_detail(stack)
    assert "<b>x</b>" not in text
    assert "&lt;b&gt;x&lt;/b&gt;" in text


async def test_invalid_callback_rejected_without_action(config):
    update, q = _update("start|not-allowlisted")
    client = MagicMock()
    await on_callback(update, _ctx(config, client))
    q.answer.assert_awaited_once()
    q.edit_message_text.assert_not_awaited()
    client.stack_action.assert_not_called()


async def test_stop_asks_for_confirmation_without_calling_api(config):
    update, q = _update("stop|media")
    client = MagicMock()
    await on_callback(update, _ctx(config, client))
    client.stack_action.assert_not_called()
    kb = q.edit_message_text.await_args.kwargs["reply_markup"]
    assert kb.inline_keyboard[0][0].callback_data == "cstop|media"


async def test_confirmed_stop_calls_api_and_rerenders(config):
    client = MagicMock()
    client.list_stacks.return_value = [
        {"name": "media", "status": "stopped", "containers": []}
    ]
    update, q = _update("cstop|media")
    await on_callback(update, _ctx(config, client))
    client.stack_action.assert_called_once_with("media", "stop")
    final_text = q.edit_message_text.await_args.args[0]
    assert "🔴" in final_text


async def test_start_calls_api(config):
    client = MagicMock()
    client.list_stacks.return_value = [
        {
            "name": "media",
            "status": "running",
            "containers": [{"name": "c", "state": "running"}],
        }
    ]
    update, _ = _update("start|media")
    await on_callback(update, _ctx(config, client))
    client.stack_action.assert_called_once_with("media", "start")


async def test_dockhand_error_reported_to_user(config):
    client = MagicMock()
    client.list_stacks.side_effect = DockhandError("Dockhand unreachable (X)")
    update, q = _update("show|media")
    await on_callback(update, _ctx(config, client))
    text = q.edit_message_text.await_args.args[0]
    assert "⚠" in text

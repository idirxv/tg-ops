from unittest.mock import AsyncMock, MagicMock

from bot.claude_handlers import on_claude_callback, render_sessions, render_version
from bot.claude_host import ClaudeHostError, ClaudeHostTimeout
from bot.claude_version import VersionCheck
from bot.sessions import Activity, Session

SESSIONS_PAYLOAD = {
    "logged_in": True,
    "sessions": [
        {"id": "dbd65fb7", "name": "greeting", "folder": "petuka-db", "status": "idle"}
    ],
}


def _ctx(config, host):
    context = MagicMock()
    context.bot_data = {"config": config, "claude_host": host}
    return context


def _update(callback_data):
    q = AsyncMock()
    q.data = callback_data
    update = MagicMock()
    update.callback_query = q
    update.effective_chat.id = 111
    return update, q


def _host(payload=SESSIONS_PAYLOAD):
    host = MagicMock()
    host.list_sessions.return_value = payload
    host.list_folders.return_value = ["alpha", "petuka-db"]
    host.version.return_value = {
        "installed": "2.1.305",
        "latest": "2.1.306",
        "channel": "latest",
    }
    host.update.return_value = {"before": "2.1.305", "after": "2.1.306"}
    return host


def test_render_empty():
    assert "No open Claude sessions" in render_sessions(True, [])


def test_render_flags_logged_out_host():
    assert "not logged in" in render_sessions(False, [])


def test_render_shows_state_folder_and_notice():
    text = render_sessions(
        True,
        [
            Session("a", "busy one", "", Activity.BUSY),
            Session("b", "idle one", "alpha", Activity.IDLE),
        ],
        notice="✅ done",
    )
    assert text.startswith("✅ done")
    assert "⚙️ <b>busy one</b> · <code>workspace root</code>" in text
    assert "💤 <b>idle one</b> · <code>alpha</code>" in text
    assert "stopped by the host" not in text


def test_render_marks_retired_sessions_and_explains_them():
    text = render_sessions(True, [Session("a", "gone", "", Activity.RETIRED)])
    assert "⏸️ <b>gone</b>" in text
    assert "stopped by the host" in text
    assert "claude attach &lt;id&gt;" in text


def test_render_escapes_html():
    text = render_sessions(True, [Session("a", "<b>x</b>", "<i>", Activity.IDLE)])
    assert "<b>x</b>" not in text
    assert "&lt;b&gt;x&lt;/b&gt;" in text
    assert "&lt;i&gt;" in text


async def test_invalid_callback_rejected_without_calling_host(config):
    host = _host()
    update, q = _update("claude.cclose|--all")
    await on_claude_callback(update, _ctx(config, host))
    q.answer.assert_awaited_once()
    q.edit_message_text.assert_not_awaited()
    host.close_session.assert_not_called()


async def test_close_asks_for_confirmation_without_closing(config):
    host = _host()
    update, q = _update("claude.close|dbd65fb7")
    await on_claude_callback(update, _ctx(config, host))
    host.close_session.assert_not_called()
    call = q.edit_message_text.await_args
    assert "greeting" in call.args[0]
    assert call.kwargs["reply_markup"].inline_keyboard[0][0].callback_data == (
        "claude.cclose|dbd65fb7"
    )


async def test_close_of_vanished_session_falls_back_to_list(config):
    host = _host({"logged_in": True, "sessions": []})
    update, q = _update("claude.close|dbd65fb7")
    await on_claude_callback(update, _ctx(config, host))
    assert "already closed" in q.edit_message_text.await_args.args[0]


async def test_close_of_retired_session_falls_back_to_list(config):
    entry = SESSIONS_PAYLOAD["sessions"][0] | {"status": None}
    host = _host({"logged_in": True, "sessions": [entry]})
    update, q = _update("claude.close|dbd65fb7")
    await on_claude_callback(update, _ctx(config, host))
    host.close_session.assert_not_called()
    assert "already stopped by the host" in q.edit_message_text.await_args.args[0]


async def test_confirmed_close_calls_host_and_rerenders(config):
    host = _host({"logged_in": True, "sessions": []})
    update, q = _update("claude.cclose|dbd65fb7")
    await on_claude_callback(update, _ctx(config, host))
    host.close_session.assert_called_once_with("dbd65fb7")
    assert "Session closed" in q.edit_message_text.await_args.args[0]


async def test_new_shows_folder_picker(config):
    update, q = _update("claude.new|")
    await on_claude_callback(update, _ctx(config, _host()))
    kb = q.edit_message_text.await_args.kwargs["reply_markup"]
    assert [row[0].callback_data for row in kb.inline_keyboard] == [
        "claude.open|",
        "claude.open|alpha",
        "claude.open|petuka-db",
        "claude.list|",
    ]


async def test_open_calls_host_with_folder(config):
    host = _host()
    update, q = _update("claude.open|petuka-db")
    await on_claude_callback(update, _ctx(config, host))
    host.open_session.assert_called_once_with("petuka-db")
    text = q.edit_message_text.await_args.args[0]
    assert "Opened a session in <b>petuka-db</b>" in text


async def test_open_in_root_passes_empty_folder(config):
    host = _host()
    update, _ = _update("claude.open|")
    await on_claude_callback(update, _ctx(config, host))
    host.open_session.assert_called_once_with("")


async def test_host_error_reported_with_recovery_buttons(config):
    host = _host()
    host.open_session.side_effect = ClaudeHostError("Claude is not logged in")
    update, q = _update("claude.open|")
    await on_claude_callback(update, _ctx(config, host))
    call = q.edit_message_text.await_args
    assert "Claude is not logged in" in call.args[0]
    refresh = call.kwargs["reply_markup"].inline_keyboard[0][0]
    assert refresh.callback_data == "claude.list|"


async def test_open_timeout_warns_before_retry(config):
    host = _host()
    host.open_session.side_effect = ClaudeHostTimeout("did not answer within 75s")
    update, q = _update("claude.open|")
    await on_claude_callback(update, _ctx(config, host))
    assert "may still be opening" in q.edit_message_text.await_args.args[0]


async def test_actions_are_audit_logged(config, caplog):
    update, q = _update("claude.cclose|dbd65fb7")
    q.from_user.id = 42
    q.from_user.username = "alice"
    host = _host({"logged_in": True, "sessions": []})
    with caplog.at_level("INFO", logger="bot.claude_handlers"):
        await on_claude_callback(update, _ctx(config, host))
    assert "close session dbd65fb7 requested by user_id=42 (@alice)" in caplog.text
    assert "Closed session dbd65fb7" in caplog.text


def test_render_version_with_update_available():
    text = render_version(VersionCheck("2.1.305", "2.1.306", "latest"))
    assert "Installed: <code>2.1.305</code>" in text
    assert "Latest: <code>2.1.306</code>" in text


def test_render_version_up_to_date():
    text = render_version(VersionCheck("2.1.305", "2.1.305", "latest"))
    assert "Installed: <code>2.1.305</code>" in text
    assert "✅" in text
    assert "Latest:" not in text


def test_render_version_when_latest_is_unknown():
    text = render_version(VersionCheck("2.1.305", None, "latest"))
    assert "Installed: <code>2.1.305</code>" in text
    assert "Couldn't check for updates" in text


async def test_check_update_shows_versions_and_update_button(config):
    host = _host()
    update, q = _update("claude.check|")
    await on_claude_callback(update, _ctx(config, host))
    call = q.edit_message_text.await_args
    assert "2.1.306" in call.args[0]
    buttons = [
        row[0].callback_data for row in call.kwargs["reply_markup"].inline_keyboard
    ]
    assert buttons == ["claude.update|", "claude.list|"]
    host.update.assert_not_called()


async def test_update_reports_versions_and_running_sessions(config):
    host = _host(
        {
            "logged_in": True,
            "sessions": [
                {"id": "dbd65fb7", "name": "a", "status": "idle"},
                {"id": "ab12cd34", "name": "b", "status": "busy"},
                {"id": "00000000", "name": "c"},  # retired: resumes on the new one
            ],
        }
    )
    update, q = _update("claude.update|")
    await on_claude_callback(update, _ctx(config, host))
    host.update.assert_called_once_with()
    assert q.edit_message_text.await_args_list[0].args[0].startswith("⏳")
    assert q.edit_message_text.await_args_list[0].kwargs["reply_markup"] is None
    text = q.edit_message_text.await_args.args[0]
    assert "2.1.305 → 2.1.306" in text
    assert "2 running sessions keep 2.1.305 until closed" in text


async def test_update_with_one_running_session_uses_singular(config):
    host = _host()
    update, q = _update("claude.update|")
    await on_claude_callback(update, _ctx(config, host))
    assert "1 running session keeps 2.1.305" in q.edit_message_text.await_args.args[0]


async def test_update_already_up_to_date(config):
    host = _host()
    host.update.return_value = {"before": "2.1.306", "after": "2.1.306"}
    update, q = _update("claude.update|")
    await on_claude_callback(update, _ctx(config, host))
    text = q.edit_message_text.await_args.args[0]
    assert "Already up to date" in text
    assert "running session" not in text


async def test_update_timeout_warns_it_may_still_run(config):
    host = _host()
    host.update.side_effect = ClaudeHostTimeout("did not answer within 180s")
    update, q = _update("claude.update|")
    await on_claude_callback(update, _ctx(config, host))
    assert "may still be running" in q.edit_message_text.await_args.args[0]


async def test_update_is_audit_logged(config, caplog):
    update, q = _update("claude.update|")
    q.from_user.id = 42
    q.from_user.username = "alice"
    with caplog.at_level("INFO", logger="bot.claude_handlers"):
        await on_claude_callback(update, _ctx(config, _host()))
    assert "update requested by user_id=42 (@alice)" in caplog.text
    assert "Updated Claude Code 2.1.305 -> 2.1.306" in caplog.text

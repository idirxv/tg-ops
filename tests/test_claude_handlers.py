from unittest.mock import AsyncMock, MagicMock

from bot.claude_handlers import (
    cmd_claude,
    on_claude_callback,
    render_retired,
    render_sessions,
    render_version,
)
from bot.claude_host import ClaudeHostError, ClaudeHostStopped, ClaudeHostTimeout
from bot.claude_version import VersionCheck
from bot.sessions import Activity, Session

SESSIONS_PAYLOAD = {
    "logged_in": True,
    "sessions": [
        {"id": "dbd65fb7", "name": "greeting", "folder": "petuka-db", "status": "idle"}
    ],
}
# The same session once its process is gone: no status.
RETIRED_PAYLOAD = {
    "logged_in": True,
    "sessions": [{"id": "dbd65fb7", "name": "greeting", "folder": "petuka-db"}],
}
TWO_RETIRED_PAYLOAD = {
    "logged_in": True,
    "sessions": [
        {"id": "dbd65fb7", "name": "greeting", "folder": "petuka-db"},
        {"id": "ab12cd34", "name": "old", "folder": "alpha"},
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
    assert "No active Claude sessions." in render_sessions(True, [])


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


def test_render_leaves_retired_sessions_off_the_main_screen():
    text = render_sessions(
        True,
        [
            Session("a", "live", "", Activity.IDLE),
            Session("b", "gone", "", Activity.RETIRED),
        ],
    )
    assert "live" in text
    assert "gone" not in text
    assert "⏸️" not in text
    assert "retired" not in text.lower()


def test_render_with_only_retired_sessions_says_none_are_active():
    text = render_sessions(True, [Session("b", "gone", "", Activity.RETIRED)])
    assert "No active Claude sessions." in text
    assert "gone" not in text


def test_render_retired_lists_retired_sessions_only():
    text = render_retired(
        [
            Session("a", "live", "", Activity.IDLE),
            Session("b", "gone", "alpha", Activity.RETIRED),
        ]
    )
    assert "⏸️ <b>gone</b> · <code>alpha</code>" in text
    assert "live" not in text
    assert "tap ▶️ to resume" in text
    # Wording must not assume why the process is gone.
    assert "memory" not in text
    assert "by the host" not in text


def test_render_retired_when_none_are():
    assert "No retired Claude sessions." in render_retired([])


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
    host = _host(RETIRED_PAYLOAD)
    update, q = _update("claude.close|dbd65fb7")
    await on_claude_callback(update, _ctx(config, host))
    host.close_session.assert_not_called()
    call = q.edit_message_text.await_args
    assert "no longer running" in call.args[0]
    assert "by the host" not in call.args[0]
    kb = call.kwargs["reply_markup"]
    assert kb.inline_keyboard[0][0].callback_data == "claude.retired|"


async def test_confirmed_close_calls_host_and_rerenders(config):
    host = _host({"logged_in": True, "sessions": []})
    update, q = _update("claude.cclose|dbd65fb7")
    await on_claude_callback(update, _ctx(config, host))
    host.close_session.assert_called_once_with("dbd65fb7")
    assert "Session closed" in q.edit_message_text.await_args.args[0]


async def test_retired_screen_lists_retired_sessions_with_resume_and_back(config):
    host = _host(
        {
            "logged_in": True,
            "sessions": [
                {"id": "dbd65fb7", "name": "live", "status": "idle"},
                {"id": "ab12cd34", "name": "gone", "folder": "alpha"},
            ],
        }
    )
    update, q = _update("claude.retired|")
    await on_claude_callback(update, _ctx(config, host))
    call = q.edit_message_text.await_args
    assert "⏸️ <b>gone</b> · <code>alpha</code>" in call.args[0]
    assert "live" not in call.args[0]
    data = [row[0].callback_data for row in call.kwargs["reply_markup"].inline_keyboard]
    assert data == ["claude.resume|ab12cd34", "claude.list|"]


async def test_stale_retired_screen_button_shows_none_left(config):
    update, q = _update("claude.retired|")
    await on_claude_callback(update, _ctx(config, _host()))
    call = q.edit_message_text.await_args
    assert "No retired Claude sessions." in call.args[0]
    data = [row[0].callback_data for row in call.kwargs["reply_markup"].inline_keyboard]
    assert data == ["claude.list|"]


async def test_resume_returns_to_main_screen_with_session_running(config):
    host = _host()
    host.list_sessions.side_effect = [RETIRED_PAYLOAD, SESSIONS_PAYLOAD]
    update, q = _update("claude.resume|dbd65fb7")
    await on_claude_callback(update, _ctx(config, host))
    host.resume_session.assert_called_once_with("dbd65fb7")
    assert q.edit_message_text.await_args_list[0].args[0].startswith("⏳")
    assert q.edit_message_text.await_args_list[0].kwargs["reply_markup"] is None
    text = q.edit_message_text.await_args.args[0]
    assert text.startswith("✅ Session resumed")
    assert "<b>greeting</b>" in text
    # Back on the main screen with its process alive, it can be closed again.
    kb = q.edit_message_text.await_args.kwargs["reply_markup"]
    assert kb.inline_keyboard[0][0].callback_data == "claude.close|dbd65fb7"


async def test_resume_of_session_no_longer_retired_refreshes_main_screen(config):
    host = _host()
    update, q = _update("claude.resume|dbd65fb7")
    await on_claude_callback(update, _ctx(config, host))
    host.resume_session.assert_not_called()
    call = q.edit_message_text.await_args
    assert "already running" in call.args[0]
    assert call.kwargs["reply_markup"].inline_keyboard[0][0].callback_data == (
        "claude.close|dbd65fb7"
    )


async def test_resume_of_vanished_session_refreshes_main_screen(config):
    host = _host({"logged_in": True, "sessions": []})
    update, q = _update("claude.resume|dbd65fb7")
    await on_claude_callback(update, _ctx(config, host))
    host.resume_session.assert_not_called()
    call = q.edit_message_text.await_args
    assert "no longer exists" in call.args[0]
    assert "No active Claude sessions." in call.args[0]


async def test_resume_reports_host_refusal(config):
    host = _host(RETIRED_PAYLOAD)
    host.resume_session.side_effect = ClaudeHostError("session is already running")
    update, q = _update("claude.resume|dbd65fb7")
    await on_claude_callback(update, _ctx(config, host))
    assert "already running" in q.edit_message_text.await_args.args[0]


async def test_resume_is_audit_logged(config, caplog):
    update, q = _update("claude.resume|dbd65fb7")
    q.from_user.id = 42
    q.from_user.username = "alice"
    with caplog.at_level("INFO", logger="bot.claude_handlers"):
        await on_claude_callback(update, _ctx(config, _host(RETIRED_PAYLOAD)))
    assert "resume session dbd65fb7 requested by user_id=42 (@alice)" in caplog.text
    assert "Resumed session dbd65fb7" in caplog.text


def test_render_retired_offers_discard_and_shows_notice():
    text = render_retired([Session("b", "gone", "", Activity.RETIRED)], "🗑 done")
    assert text.startswith("🗑 done")
    assert "🗑 to discard" in text


async def test_discard_asks_for_confirmation_warning_the_conversation_is_lost(config):
    host = _host(RETIRED_PAYLOAD)
    update, q = _update("claude.discard|dbd65fb7")
    await on_claude_callback(update, _ctx(config, host))
    host.discard_session.assert_not_called()
    call = q.edit_message_text.await_args
    assert "<b>greeting</b>" in call.args[0]
    assert "conversation is deleted for good" in call.args[0]
    data = [b.callback_data for b in call.kwargs["reply_markup"].inline_keyboard[0]]
    assert data == ["claude.cdiscard|dbd65fb7", "claude.retired|"]


async def test_discard_of_running_session_points_to_close(config):
    host = _host()
    update, q = _update("claude.discard|dbd65fb7")
    await on_claude_callback(update, _ctx(config, host))
    host.discard_session.assert_not_called()
    call = q.edit_message_text.await_args
    assert "close it instead" in call.args[0]
    assert call.kwargs["reply_markup"].inline_keyboard[0][0].callback_data == (
        "claude.close|dbd65fb7"
    )


async def test_discard_of_vanished_session_refreshes_retired_screen(config):
    host = _host(TWO_RETIRED_PAYLOAD)
    update, q = _update("claude.discard|00000000")
    await on_claude_callback(update, _ctx(config, host))
    host.discard_session.assert_not_called()
    call = q.edit_message_text.await_args
    assert "no longer exists" in call.args[0]
    assert "<b>greeting</b>" in call.args[0]


async def test_confirmed_discard_stays_on_retired_screen_while_some_remain(config):
    # ab12cd34 is gone once Discarded; dbd65fb7 is still Retired.
    host = _host(RETIRED_PAYLOAD)
    update, q = _update("claude.cdiscard|ab12cd34")
    await on_claude_callback(update, _ctx(config, host))
    host.discard_session.assert_called_once_with("ab12cd34")
    assert q.edit_message_text.await_args_list[0].args[0].startswith("⏳")
    assert q.edit_message_text.await_args_list[0].kwargs["reply_markup"] is None
    call = q.edit_message_text.await_args
    assert call.args[0].startswith("🗑 Session discarded.")
    assert "<b>Retired sessions</b>" in call.args[0]
    data = [row[0].callback_data for row in call.kwargs["reply_markup"].inline_keyboard]
    assert data == ["claude.resume|dbd65fb7", "claude.list|"]


async def test_confirmed_discard_of_last_retired_returns_to_main_screen(config):
    host = _host(SESSIONS_PAYLOAD)
    update, q = _update("claude.cdiscard|ab12cd34")
    await on_claude_callback(update, _ctx(config, host))
    host.discard_session.assert_called_once_with("ab12cd34")
    call = q.edit_message_text.await_args
    assert call.args[0].startswith("🗑 Session discarded.")
    assert "<b>Claude sessions</b>" in call.args[0]
    kb = call.kwargs["reply_markup"]
    assert kb.inline_keyboard[0][0].callback_data == "claude.close|dbd65fb7"


async def test_discard_reports_host_refusal(config):
    host = _host(RETIRED_PAYLOAD)
    host.discard_session.side_effect = ClaudeHostError(
        "session is running: close it instead"
    )
    update, q = _update("claude.cdiscard|dbd65fb7")
    await on_claude_callback(update, _ctx(config, host))
    assert "close it instead" in q.edit_message_text.await_args.args[0]


async def test_discard_is_audit_logged(config, caplog):
    update, q = _update("claude.cdiscard|dbd65fb7")
    q.from_user.id = 42
    q.from_user.username = "alice"
    with caplog.at_level("INFO", logger="bot.claude_handlers"):
        await on_claude_callback(update, _ctx(config, _host()))
    assert "discard session dbd65fb7 requested by user_id=42 (@alice)" in caplog.text
    assert "Discarded session dbd65fb7" in caplog.text


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


async def test_button_while_host_stopped_says_so_and_refresh_reloads(config):
    host = _host()
    host.list_sessions.side_effect = ClaudeHostStopped()
    update, q = _update("claude.list|")
    await on_claude_callback(update, _ctx(config, host))
    call = q.edit_message_text.await_args
    assert "Claude Host is stopped — start its stack from /docker" in call.args[0]
    refresh = call.kwargs["reply_markup"].inline_keyboard[0][0]
    assert refresh.text == "🔄 Refresh"

    # The Claude Host is back: Refresh reloads the panel.
    host.list_sessions.side_effect = None
    update, q = _update(refresh.callback_data)
    await on_claude_callback(update, _ctx(config, host))
    assert "greeting" in q.edit_message_text.await_args.args[0]


async def test_command_while_host_stopped_says_so_with_refresh(config):
    host = _host()
    host.list_sessions.side_effect = ClaudeHostStopped()
    update = MagicMock()
    update.effective_message.reply_text = AsyncMock()
    await cmd_claude(update, _ctx(config, host))
    call = update.effective_message.reply_text.await_args
    assert "Claude Host is stopped — start its stack from /docker" in call.args[0]
    refresh = call.kwargs["reply_markup"].inline_keyboard[0][0]
    assert (refresh.text, refresh.callback_data) == ("🔄 Refresh", "claude.list|")


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

"""Telegram handlers for the /claude panel: list, open, close and resume
Sessions, and Update Claude Code on the Claude Host."""
from __future__ import annotations

import asyncio
import html
import logging

from telegram import CallbackQuery, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from bot.claude_host import ClaudeHostClient, ClaudeHostError, ClaudeHostTimeout
from bot.claude_keyboards import (
    ClaudeAction,
    confirm_close_keyboard,
    decode,
    error_keyboard,
    folder_keyboard,
    sessions_keyboard,
    version_keyboard,
)
from bot.claude_version import VersionCheck, parse_update, parse_version_check
from bot.handlers import safe_edit
from bot.keyboards import CallbackError
from bot.sessions import Activity, Session, parse_sessions

log = logging.getLogger(__name__)

_ICONS = {Activity.BUSY: "⚙️", Activity.IDLE: "💤", Activity.RETIRED: "⏸️"}


def _host(context: ContextTypes.DEFAULT_TYPE) -> ClaudeHostClient:
    return context.bot_data["claude_host"]


def render_sessions(logged_in: bool, sessions: list[Session], notice: str = "") -> str:
    lines = [notice] if notice else []
    if not logged_in:
        lines.append(
            "⚠️ Claude is not logged in on the host — log in from its terminal."
        )
    if not sessions:
        lines.append("No open Claude sessions.")
    else:
        lines.append("<b>Claude sessions</b> — tap ⏹ to close one.")
        for s in sessions:
            icon = _ICONS[s.activity]
            folder = html.escape(s.folder) or "workspace root"
            lines.append(f"{icon} <b>{html.escape(s.name)}</b> · <code>{folder}</code>")
        if any(s.activity is Activity.RETIRED for s in sessions):
            lines.append(
                "⏸️ = stopped by the host while waiting for you. Its conversation "
                "is kept: tap ▶️ to resume it."
            )
    return "\n".join(lines)


def render_version(check: VersionCheck) -> str:
    lines = [
        "<b>Claude Code</b>",
        f"Installed: <code>{html.escape(check.installed)}</code>",
    ]
    if check.latest is None:
        lines.append("⚠️ Couldn't check for updates.")
    elif check.update_available:
        lines.append(f"Latest: <code>{html.escape(check.latest)}</code>")
    else:
        lines.append(f"✅ Latest on the {html.escape(check.channel)} channel.")
    return "\n".join(lines)


async def _fetch_sessions(
    context: ContextTypes.DEFAULT_TYPE,
) -> tuple[bool, list[Session]]:
    payload = await asyncio.to_thread(_host(context).list_sessions)
    return parse_sessions(payload)


async def _show_list(
    query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE, notice: str = ""
) -> None:
    logged_in, sessions = await _fetch_sessions(context)
    await safe_edit(
        query, render_sessions(logged_in, sessions, notice), sessions_keyboard(sessions)
    )


async def _show_folders(
    query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE
) -> None:
    folders = await asyncio.to_thread(_host(context).list_folders)
    await safe_edit(query, "Open a session in which folder?", folder_keyboard(folders))


async def _confirm_close(
    query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE, session_id: str
) -> None:
    _, sessions = await _fetch_sessions(context)
    session = next((s for s in sessions if s.id == session_id), None)
    if session is None:
        await _show_list(query, context, "That session is already closed.")
        return
    if session.activity is Activity.RETIRED:
        await _show_list(
            query,
            context,
            "That session was already stopped by the host: tap ▶️ to resume it.",
        )
        return
    await safe_edit(
        query,
        f"Close <b>{html.escape(session.name)}</b>? Its conversation is kept.",
        confirm_close_keyboard(session_id),
    )


def _audit(query: CallbackQuery, what: str) -> None:
    user = query.from_user
    chat_id = query.message.chat.id if query.message else "?"
    log.info(
        "Claude %s requested by user_id=%s (%s) in chat_id=%s",
        what,
        user.id,
        f"@{user.username}" if user.username else user.full_name,
        chat_id,
    )


async def _open_session(
    query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE, folder: str
) -> None:
    where = html.escape(folder) or "the workspace root"
    _audit(query, f"open session in {folder or '/'!r}")
    await safe_edit(query, f"⏳ Opening a session in <b>{where}</b>…", None)
    try:
        await asyncio.to_thread(_host(context).open_session, folder)
    except ClaudeHostTimeout as exc:
        log.warning("Open session in %r timed out: %s", folder, exc)
        # Retrying blindly could open two sessions.
        raise ClaudeHostError(
            f"{exc}. The session may still be opening: tap Refresh before retrying."
        ) from exc
    log.info("Opened session in %r", folder)
    await _show_list(query, context, f"✅ Opened a session in <b>{where}</b>.")


async def _close_session(
    query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE, session_id: str
) -> None:
    _audit(query, f"close session {session_id}")
    await safe_edit(query, f"⏳ Closing <code>{session_id}</code>…", None)
    await asyncio.to_thread(_host(context).close_session, session_id)
    log.info("Closed session %s", session_id)
    await _show_list(query, context, "✅ Session closed.")


async def _resume_session(
    query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE, session_id: str
) -> None:
    _audit(query, f"resume session {session_id}")
    await safe_edit(query, f"⏳ Resuming <code>{session_id}</code>…", None)
    await asyncio.to_thread(_host(context).resume_session, session_id)
    log.info("Resumed session %s", session_id)
    await _show_list(
        query, context, "✅ Session resumed: answer it from the Claude app."
    )


async def _check_update(
    query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE
) -> None:
    check = parse_version_check(await asyncio.to_thread(_host(context).version))
    await safe_edit(query, render_version(check), version_keyboard(check))


async def _update_claude(
    query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE
) -> None:
    _audit(query, "update")
    await safe_edit(query, "⏳ Updating Claude Code…", None)
    try:
        payload = await asyncio.to_thread(_host(context).update)
    except ClaudeHostTimeout as exc:
        log.warning("Claude Code update timed out: %s", exc)
        raise ClaudeHostError(
            f"{exc}. The update may still be running: check again in a minute."
        ) from exc
    result = parse_update(payload)
    log.info("Updated Claude Code %s -> %s", result.before, result.after)
    if not result.changed:
        notice = f"✅ Already up to date ({html.escape(result.after)})."
    else:
        notice = (
            f"✅ Updated Claude Code {html.escape(result.before)} → "
            f"{html.escape(result.after)}."
        )
    logged_in, sessions = await _fetch_sessions(context)
    # Retired sessions have no process left: they resume on the new version.
    running = sum(s.activity is not Activity.RETIRED for s in sessions)
    if result.changed and running:
        keep = "session keeps" if running == 1 else "sessions keep"
        notice += (
            f" {running} running {keep} {html.escape(result.before)} until closed."
        )
    await safe_edit(
        query, render_sessions(logged_in, sessions, notice), sessions_keyboard(sessions)
    )


async def cmd_claude(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message is None:  # CommandHandler always carries one
        return
    try:
        logged_in, sessions = await _fetch_sessions(context)
    except (ClaudeHostError, ValueError) as exc:
        log.error("/claude failed: %s", exc)
        await message.reply_text(f"⚠️ {exc}")
        return
    await message.reply_text(
        render_sessions(logged_in, sessions),
        reply_markup=sessions_keyboard(sessions),
        parse_mode=ParseMode.HTML,
    )


async def on_claude_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    if query is None:  # CallbackQueryHandler always carries one
        return
    try:
        action, arg = decode(query.data)
    except CallbackError as exc:
        chat = update.effective_chat
        log.warning(
            "Rejected callback from chat_id=%s: %s", chat.id if chat else "?", exc
        )
        await query.answer("Expired or invalid — send /claude", show_alert=True)
        return

    await query.answer()
    try:
        if action is ClaudeAction.LIST:
            await _show_list(query, context)
        elif action is ClaudeAction.NEW:
            await _show_folders(query, context)
        elif action is ClaudeAction.OPEN:
            await _open_session(query, context, arg)
        elif action is ClaudeAction.CLOSE:
            await _confirm_close(query, context, arg)
        elif action is ClaudeAction.CONFIRM_CLOSE:
            await _close_session(query, context, arg)
        elif action is ClaudeAction.RESUME:
            await _resume_session(query, context, arg)
        elif action is ClaudeAction.CHECK_UPDATE:
            await _check_update(query, context)
        elif action is ClaudeAction.UPDATE:
            await _update_claude(query, context)
        else:  # EXIT
            await query.delete_message()
    except (ClaudeHostError, ValueError) as exc:
        log.error("Callback %r failed: %s", query.data, exc)
        await safe_edit(query, f"⚠️ {html.escape(str(exc))}", error_keyboard())

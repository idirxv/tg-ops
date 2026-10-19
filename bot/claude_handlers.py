"""Telegram handlers for the /claude panel: list, open and close Sessions."""
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
)
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
        lines.append("<b>Claude sessions</b> — tap one to close it.")
        for s in sessions:
            icon = _ICONS[s.activity]
            folder = html.escape(s.folder) or "workspace root"
            lines.append(f"{icon} <b>{html.escape(s.name)}</b> · <code>{folder}</code>")
        if any(s.activity is Activity.RETIRED for s in sessions):
            lines.append(
                "⏸️ = stopped by the host while waiting for you. Its conversation "
                "is kept: resume it on the host with "
                "<code>claude attach &lt;id&gt;</code>."
            )
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
            query, context, "That session was already stopped by the host."
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
        else:  # EXIT
            await query.delete_message()
    except (ClaudeHostError, ValueError) as exc:
        log.error("Callback %r failed: %s", query.data, exc)
        await safe_edit(query, f"⚠️ {html.escape(str(exc))}", error_keyboard())

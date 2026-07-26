"""Telegram handlers: /ping, /docker commands, callback dispatch, rendering."""
from __future__ import annotations

import asyncio
import html
import logging

from telegram import CallbackQuery, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from bot.config import Config
from bot.dockhand import DockhandClient, DockhandError
from bot.keyboards import (
    Action,
    CallbackError,
    confirm_stop_keyboard,
    decode,
    stack_detail_keyboard,
    stack_list_keyboard,
)
from bot.stacks import STATUS_DOT, Stack, StackStatus, parse_stacks

log = logging.getLogger(__name__)

# Action -> (Dockhand endpoint verb, progress wording)
_ACTIONS = {
    Action.START: ("start", "Starting"),
    Action.CONFIRM_STOP: ("stop", "Stopping"),
    Action.RESTART: ("restart", "Restarting"),
}


def _config(context: ContextTypes.DEFAULT_TYPE) -> Config:
    return context.bot_data["config"]


def _client(context: ContextTypes.DEFAULT_TYPE) -> DockhandClient:
    return context.bot_data["client"]


def render_list(stacks: list[Stack]) -> str:
    if not stacks:
        return "No controllable stacks found in Dockhand."
    return "<b>Stacks</b> — tap one to manage it."


def _container_dot(state: str) -> str:
    running = state == "running"
    return STATUS_DOT[StackStatus.RUNNING if running else StackStatus.STOPPED]


def render_detail(stack: Stack) -> str:
    lines = [
        f"{STATUS_DOT[stack.status]} <b>{html.escape(stack.name)}</b>"
        f" — {stack.status.value}"
    ]
    for c in stack.containers:
        lines.append(
            f"{_container_dot(c.state)} <code>{html.escape(c.name)}</code>"
            f" ({html.escape(c.state)})"
        )
    if not stack.containers:
        lines.append("<i>no containers</i>")
    return "\n".join(lines)


async def _fetch_stacks(context: ContextTypes.DEFAULT_TYPE) -> list[Stack]:
    payload = await asyncio.to_thread(_client(context).list_stacks)
    return parse_stacks(payload, _config(context).allowed_stacks)


async def _fetch_stack(context: ContextTypes.DEFAULT_TYPE, name: str) -> Stack | None:
    stacks = await _fetch_stacks(context)
    return next((s for s in stacks if s.name == name), None)


async def _safe_edit(
    query: CallbackQuery, text: str, keyboard: InlineKeyboardMarkup | None
) -> None:
    """Edit the callback message, ignoring Telegram's 'message is not
    modified' complaint (e.g. Refresh with unchanged status)."""
    try:
        await query.edit_message_text(
            text, reply_markup=keyboard, parse_mode=ParseMode.HTML
        )
    except BadRequest as exc:
        if "not modified" not in str(exc).lower():
            raise


async def _show_list(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE) -> None:
    stacks = await _fetch_stacks(context)
    await _safe_edit(query, render_list(stacks), stack_list_keyboard(stacks))


async def _show_detail(
    query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE, name: str
) -> None:
    stack = await _fetch_stack(context, name)
    if stack is None:
        await _safe_edit(
            query,
            f"⚠️ Stack <b>{html.escape(name)}</b> not found in Dockhand.",
            stack_list_keyboard([]),
        )
        return
    await _safe_edit(query, render_detail(stack), stack_detail_keyboard(stack))


async def _run_action(
    query: CallbackQuery,
    context: ContextTypes.DEFAULT_TYPE,
    action: Action,
    name: str,
) -> None:
    verb, wording = _ACTIONS[action]
    await _safe_edit(
        query,
        f"⏳ {wording} <b>{html.escape(name)}</b>…",
        None,  # no buttons while the action runs: prevents double-taps
    )
    await asyncio.to_thread(_client(context).stack_action, name, verb)
    await _show_detail(query, context, name)


async def cmd_ping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message is None:  # CommandHandler always carries one
        return
    await message.reply_text("Pong")


async def cmd_docker(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message is None:  # CommandHandler always carries one
        return
    try:
        stacks = await _fetch_stacks(context)
    except (DockhandError, ValueError) as exc:
        log.error("/docker failed: %s", exc)
        await message.reply_text(f"⚠️ {exc}")
        return
    await message.reply_text(
        render_list(stacks),
        reply_markup=stack_list_keyboard(stacks),
        parse_mode=ParseMode.HTML,
    )


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None:  # CallbackQueryHandler always carries one
        return
    try:
        action, stack_name = decode(query.data, _config(context).allowed_stacks)
    except CallbackError as exc:
        chat = update.effective_chat
        log.warning(
            "Rejected callback from chat_id=%s: %s", chat.id if chat else "?", exc
        )
        await query.answer("Expired or invalid — send /docker", show_alert=True)
        return

    await query.answer()
    try:
        if action is Action.LIST:
            await _show_list(query, context)
        elif action is Action.SHOW:
            await _show_detail(query, context, stack_name)
        elif action is Action.STOP:
            await _safe_edit(
                query,
                f"Stop <b>{html.escape(stack_name)}</b>?",
                confirm_stop_keyboard(stack_name),
            )
        elif action is Action.EXIT:
            await query.delete_message()
        else:  # START, CONFIRM_STOP, RESTART — validated by decode()
            await _run_action(query, context, action, stack_name)
    except (DockhandError, ValueError) as exc:
        log.error("Callback %r failed: %s", query.data, exc)
        await _safe_edit(
            query,
            f"⚠️ {html.escape(str(exc))}\n\nSend /docker to reload.",
            None,
        )


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    log.error("Unhandled error", exc_info=context.error)

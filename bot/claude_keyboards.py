"""Inline keyboards and callback-data codec for the /claude panel.

Callback data format: ``claude.<action>|<arg>``, the same shape as the stack
codec in ``bot.keyboards``. The ``claude.`` prefix routes it to this panel's
handler. ``decode`` checks the shape only: a session id must look like one,
and a folder name is re-checked against the live folder list by the control
service, which is the real boundary.
"""
from __future__ import annotations

import logging
from collections.abc import Sequence
from enum import StrEnum

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from bot.claude_version import VersionCheck
from bot.keyboards import SEP, CallbackError
from bot.sessions import SESSION_ID, Activity, Session

log = logging.getLogger(__name__)

PATTERN = r"^claude\."
# Telegram caps callback_data at 64 bytes.
_MAX_CALLBACK_BYTES = 64
# Telegram allows 100 buttons per keyboard; leave room for the nav row.
_MAX_FOLDER_BUTTONS = 90


class ClaudeAction(StrEnum):
    LIST = "claude.list"
    NEW = "claude.new"  # opens the folder picker
    OPEN = "claude.open"  # opens a session in the folder it carries
    CLOSE = "claude.close"  # asks for confirmation
    CONFIRM_CLOSE = "claude.cclose"  # actually closes
    RESUME = "claude.resume"  # restarts a Retired session's process
    CHECK_UPDATE = "claude.check"  # shows the Installed and latest versions
    # Updates to the newest release; it carries no version to pick.
    UPDATE = "claude.update"
    EXIT = "claude.exit"


def encode(action: ClaudeAction, arg: str = "") -> str:
    return f"{action.value}{SEP}{arg}"


def decode(data: str | None) -> tuple[ClaudeAction, str]:
    if not data or SEP not in data:
        raise CallbackError(f"malformed callback data: {data!r}")
    raw_action, arg = data.split(SEP, 1)
    try:
        action = ClaudeAction(raw_action)
    except ValueError as exc:
        raise CallbackError(f"unknown action: {raw_action!r}") from exc
    if action in (ClaudeAction.CLOSE, ClaudeAction.CONFIRM_CLOSE, ClaudeAction.RESUME):
        if not SESSION_ID.fullmatch(arg):
            raise CallbackError(f"invalid session id: {arg!r}")
    elif action is not ClaudeAction.OPEN and arg:
        raise CallbackError(f"{action.value} action carries no argument")
    return action, arg


def _button(label: str, action: ClaudeAction, arg: str = "") -> InlineKeyboardButton:
    return InlineKeyboardButton(label, callback_data=encode(action, arg))


def _nav_row() -> list[InlineKeyboardButton]:
    return [
        _button("🆕 New", ClaudeAction.NEW),
        _button("🔄 Refresh", ClaudeAction.LIST),
        _button("🚪 Exit", ClaudeAction.EXIT),
    ]


def sessions_keyboard(sessions: Sequence[Session]) -> InlineKeyboardMarkup:
    # A retired session has no process left for `claude stop` to close.
    rows = [
        [_button(f"▶️ {s.name}", ClaudeAction.RESUME, s.id)]
        if s.activity is Activity.RETIRED
        else [_button(f"⏹ {s.name}", ClaudeAction.CLOSE, s.id)]
        for s in sessions
    ]
    rows.append(_nav_row())
    rows.append([_button("🔄 Check update", ClaudeAction.CHECK_UPDATE)])
    return InlineKeyboardMarkup(rows)


def version_keyboard(check: VersionCheck) -> InlineKeyboardMarkup:
    rows = []
    if check.update_available:
        rows.append([_button(f"⬆️ Update to {check.latest}", ClaudeAction.UPDATE)])
    rows.append([_button("⬅️ Back", ClaudeAction.LIST)])
    return InlineKeyboardMarkup(rows)


def folder_keyboard(folders: Sequence[str]) -> InlineKeyboardMarkup:
    rows = [[_button("📂 Workspace root", ClaudeAction.OPEN)]]
    for folder in folders[:_MAX_FOLDER_BUTTONS]:
        data = encode(ClaudeAction.OPEN, folder)
        if len(data.encode()) > _MAX_CALLBACK_BYTES:
            log.warning("Folder %r too long for a button, skipping", folder)
            continue
        rows.append([InlineKeyboardButton(f"📁 {folder}", callback_data=data)])
    rows.append([_button("⬅️ Back", ClaudeAction.LIST)])
    return InlineKeyboardMarkup(rows)


def confirm_close_keyboard(session_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                _button("✅ Yes, close", ClaudeAction.CONFIRM_CLOSE, session_id),
                _button("❌ Cancel", ClaudeAction.LIST),
            ]
        ]
    )


def error_keyboard() -> InlineKeyboardMarkup:
    """Recovery buttons after a failure: reload the panel, or leave it."""
    return InlineKeyboardMarkup(
        [
            [
                _button("🔄 Refresh", ClaudeAction.LIST),
                _button("🚪 Exit", ClaudeAction.EXIT),
            ]
        ]
    )

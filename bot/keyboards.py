"""Inline keyboards and the callback-data codec.

Callback data format: ``<action>|<stack>``. Telegram callback data is
client-forgeable, so ``decode`` is the security boundary: unknown actions
and non-allowlisted stacks are rejected with ``CallbackError``.
"""
from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from bot.stacks import STATUS_DOT, Stack, StackStatus

SEP = "|"


class Action(StrEnum):
    LIST = "list"
    SHOW = "show"
    START = "start"
    STOP = "stop"  # asks for confirmation
    CONFIRM_STOP = "cstop"  # actually stops
    RESTART = "restart"
    EXIT = "exit"


class CallbackError(ValueError):
    """Callback data failed validation."""


def encode(action: Action, stack: str = "") -> str:
    return f"{action.value}{SEP}{stack}"


def decode(data: str | None, allowed_stacks: Sequence[str]) -> tuple[Action, str]:
    if not data or SEP not in data:
        raise CallbackError(f"malformed callback data: {data!r}")
    raw_action, stack = data.split(SEP, 1)
    try:
        action = Action(raw_action)
    except ValueError as exc:
        raise CallbackError(f"unknown action: {raw_action!r}") from exc
    if action in (Action.LIST, Action.EXIT):
        if stack:
            raise CallbackError(f"{action.value} action carries no stack")
        return action, ""
    if stack not in allowed_stacks:
        raise CallbackError(f"stack not allowlisted: {stack!r}")
    return action, stack


def _button(label: str, action: Action, stack: str = "") -> InlineKeyboardButton:
    return InlineKeyboardButton(label, callback_data=encode(action, stack))


def stack_list_keyboard(stacks: Sequence[Stack]) -> InlineKeyboardMarkup:
    rows = [
        [_button(f"{STATUS_DOT[s.status]} {s.name}", Action.SHOW, s.name)]
        for s in stacks
    ]
    rows.append([_button("🔄 Refresh", Action.LIST), _button("🚪 Exit", Action.EXIT)])
    return InlineKeyboardMarkup(rows)


def stack_detail_keyboard(stack: Stack) -> InlineKeyboardMarkup:
    actions: list[InlineKeyboardButton] = []
    if stack.status is not StackStatus.RUNNING:
        actions.append(_button("▶️ Start", Action.START, stack.name))
    if stack.status is not StackStatus.STOPPED:
        actions.append(_button("⏹ Stop", Action.STOP, stack.name))
        actions.append(_button("🔁 Restart", Action.RESTART, stack.name))
    return InlineKeyboardMarkup(
        [
            actions,
            [
                _button("🔄 Refresh", Action.SHOW, stack.name),
                _button("⬅️ Back", Action.LIST),
            ],
        ]
    )


def confirm_stop_keyboard(stack_name: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                _button("✅ Yes, stop", Action.CONFIRM_STOP, stack_name),
                _button("❌ Cancel", Action.SHOW, stack_name),
            ]
        ]
    )

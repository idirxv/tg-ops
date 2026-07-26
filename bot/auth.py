"""Chat-ID allowlist enforcement.

The gate runs as a ``TypeHandler`` in group -1, before all other handlers,
so it covers messages AND callback queries. Unauthorized updates are
dropped silently (no reply) and logged.
"""
from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ApplicationHandlerStop, ContextTypes

log = logging.getLogger(__name__)


def is_authorized(update: Update, allowed_chat_ids: frozenset[int]) -> bool:
    chat = update.effective_chat
    return chat is not None and chat.id in allowed_chat_ids


def make_auth_gate(allowed_chat_ids: frozenset[int]):
    async def gate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not is_authorized(update, allowed_chat_ids):
            chat = update.effective_chat
            log.warning("Denied update from chat_id=%s", chat.id if chat else "<none>")
            raise ApplicationHandlerStop

    return gate

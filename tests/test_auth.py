from types import SimpleNamespace

import pytest
from telegram.ext import ApplicationHandlerStop

from bot.auth import is_authorized, make_auth_gate

ALLOWED = frozenset({111})


def _update(chat_id):
    chat = SimpleNamespace(id=chat_id) if chat_id is not None else None
    return SimpleNamespace(effective_chat=chat)


def test_allowed_chat():
    assert is_authorized(_update(111), ALLOWED)


def test_denied_chat():
    assert not is_authorized(_update(999), ALLOWED)


def test_update_without_chat_denied():
    assert not is_authorized(_update(None), ALLOWED)


async def test_gate_passes_allowed_update():
    gate = make_auth_gate(ALLOWED)
    await gate(_update(111), None)  # must not raise


async def test_gate_blocks_denied_update():
    gate = make_auth_gate(ALLOWED)
    with pytest.raises(ApplicationHandlerStop):
        await gate(_update(999), None)

import pytest

from bot.keyboards import (
    Action,
    CallbackError,
    confirm_stop_keyboard,
    decode,
    encode,
    stack_detail_keyboard,
    stack_list_keyboard,
)
from bot.stacks import Stack, StackStatus

ALLOWED = ("media", "vpn")


def test_round_trip():
    assert decode(encode(Action.START, "media"), ALLOWED) == (Action.START, "media")
    assert decode(encode(Action.LIST), ALLOWED) == (Action.LIST, "")
    assert decode(encode(Action.EXIT), ALLOWED) == (Action.EXIT, "")


def test_unknown_action_rejected():
    with pytest.raises(CallbackError):
        decode("hack|media", ALLOWED)


def test_forged_stack_rejected():
    with pytest.raises(CallbackError):
        decode("start|secret", ALLOWED)


@pytest.mark.parametrize("data", [None, "", "start", "||", "list|extra"])
def test_garbage_rejected(data):
    with pytest.raises(CallbackError):
        decode(data, ALLOWED)


def _stack(status):
    return Stack(name="media", status=status)


def test_list_keyboard_dots_and_refresh():
    kb = stack_list_keyboard(
        [Stack("media", StackStatus.RUNNING), Stack("vpn", StackStatus.STOPPED)]
    )
    texts = [b.text for row in kb.inline_keyboard for b in row]
    assert texts == ["🟢 media", "🔴 vpn", "🔄 Refresh", "🚪 Exit"]
    assert kb.inline_keyboard[0][0].callback_data == "show|media"
    assert [b.callback_data for b in kb.inline_keyboard[-1]] == ["list|", "exit|"]


def test_detail_keyboard_stopped_has_only_start():
    kb = stack_detail_keyboard(_stack(StackStatus.STOPPED))
    assert [b.callback_data for b in kb.inline_keyboard[0]] == ["start|media"]


def test_detail_keyboard_running_has_stop_and_restart():
    kb = stack_detail_keyboard(_stack(StackStatus.RUNNING))
    assert [b.callback_data for b in kb.inline_keyboard[0]] == [
        "stop|media",
        "restart|media",
    ]


def test_detail_keyboard_partial_has_all_three():
    kb = stack_detail_keyboard(_stack(StackStatus.PARTIAL))
    assert [b.callback_data for b in kb.inline_keyboard[0]] == [
        "start|media",
        "stop|media",
        "restart|media",
    ]


def test_detail_keyboard_always_has_refresh_and_back():
    kb = stack_detail_keyboard(_stack(StackStatus.RUNNING))
    assert [b.callback_data for b in kb.inline_keyboard[1]] == ["show|media", "list|"]


def test_confirm_keyboard():
    kb = confirm_stop_keyboard("media")
    yes, cancel = kb.inline_keyboard[0]
    assert yes.callback_data == "cstop|media"
    assert cancel.callback_data == "show|media"

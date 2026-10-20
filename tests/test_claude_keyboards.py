import pytest

from bot.claude_keyboards import (
    ClaudeAction,
    confirm_close_keyboard,
    decode,
    encode,
    folder_keyboard,
    sessions_keyboard,
    version_keyboard,
)
from bot.claude_version import VersionCheck
from bot.keyboards import CallbackError
from bot.sessions import Activity, Session


@pytest.mark.parametrize(
    ("action", "arg"),
    [
        (ClaudeAction.LIST, ""),
        (ClaudeAction.NEW, ""),
        (ClaudeAction.EXIT, ""),
        (ClaudeAction.OPEN, ""),
        (ClaudeAction.OPEN, "petuka-db"),
        (ClaudeAction.CLOSE, "dbd65fb7"),
        (ClaudeAction.CONFIRM_CLOSE, "dbd65fb7"),
        (ClaudeAction.CHECK_UPDATE, ""),
        (ClaudeAction.UPDATE, ""),
    ],
)
def test_roundtrip(action, arg):
    assert decode(encode(action, arg)) == (action, arg)


@pytest.mark.parametrize(
    "data",
    [
        None,
        "",
        "claude.list",  # no separator
        "list|",  # stack action, not ours
        "claude.nope|",
        "claude.list|extra",  # argument-less action carrying one
        "claude.close|",
        "claude.close|--all",
        "claude.cclose|DBD65FB7",
        "claude.cclose|dbd65fb7;ls",
        "claude.update|2.1.306",  # always installs the newest, never a pick
        "claude.check|x",
    ],
)
def test_decode_rejects_forged_data(data):
    with pytest.raises(CallbackError):
        decode(data)


def test_folder_may_contain_the_separator():
    assert decode("claude.open|a|b") == (ClaudeAction.OPEN, "a|b")


def test_sessions_keyboard_has_close_rows_nav_and_check_update():
    kb = sessions_keyboard(
        [
            Session("dbd65fb7", "one", "", Activity.IDLE),
            Session("ab12cd34", "gone", "", Activity.RETIRED),
        ]
    )
    assert len(kb.inline_keyboard) == 3  # the retired session has no close row
    assert kb.inline_keyboard[0][0].callback_data == "claude.close|dbd65fb7"
    nav = [b.callback_data for b in kb.inline_keyboard[-2]]
    assert nav == ["claude.new|", "claude.list|", "claude.exit|"]
    assert [b.callback_data for b in kb.inline_keyboard[-1]] == ["claude.check|"]


def test_folder_keyboard_leads_with_root_and_skips_oversized_names():
    kb = folder_keyboard(["alpha", "x" * 60])
    data = [row[0].callback_data for row in kb.inline_keyboard]
    assert data == ["claude.open|", "claude.open|alpha", "claude.list|"]
    assert all(len(d.encode()) <= 64 for d in data)


def test_folder_keyboard_caps_button_count():
    kb = folder_keyboard([f"f{i}" for i in range(500)])
    assert sum(len(row) for row in kb.inline_keyboard) <= 100


def test_confirm_close_keyboard():
    kb = confirm_close_keyboard("dbd65fb7")
    assert kb.inline_keyboard[0][0].callback_data == "claude.cclose|dbd65fb7"
    assert kb.inline_keyboard[0][1].callback_data == "claude.list|"


def test_version_keyboard_offers_update_only_when_one_is_available():
    kb = version_keyboard(VersionCheck("2.1.305", "2.1.306", "latest"))
    data = [row[0].callback_data for row in kb.inline_keyboard]
    assert data == ["claude.update|", "claude.list|"]
    assert "2.1.306" in kb.inline_keyboard[0][0].text
    for latest in ("2.1.305", None):
        kb = version_keyboard(VersionCheck("2.1.305", latest, "latest"))
        assert [row[0].callback_data for row in kb.inline_keyboard] == ["claude.list|"]

import pytest

from bot.claude_keyboards import (
    ClaudeAction,
    confirm_close_keyboard,
    decode,
    encode,
    folder_keyboard,
    retired_keyboard,
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
        (ClaudeAction.RESUME, "dbd65fb7"),
        (ClaudeAction.RETIRED, ""),
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
        "claude.resume|",
        "claude.resume|--all",
        "claude.update|2.1.306",  # always installs the newest, never a pick
        "claude.check|x",
        "claude.retired|dbd65fb7",
    ],
)
def test_decode_rejects_forged_data(data):
    with pytest.raises(CallbackError):
        decode(data)


def test_folder_may_contain_the_separator():
    assert decode("claude.open|a|b") == (ClaudeAction.OPEN, "a|b")


def test_sessions_keyboard_lists_running_sessions_only():
    kb = sessions_keyboard(
        [
            Session("dbd65fb7", "one", "", Activity.IDLE),
            Session("ab12cd34", "gone", "", Activity.RETIRED),
            Session("ef56ab78", "two", "", Activity.BUSY),
        ]
    )
    data = [[b.callback_data for b in row] for row in kb.inline_keyboard]
    assert data == [
        ["claude.close|dbd65fb7"],
        ["claude.close|ef56ab78"],
        ["claude.retired|"],
        ["claude.new|", "claude.list|", "claude.exit|"],
        ["claude.check|"],
    ]
    assert kb.inline_keyboard[2][0].text == "⏸️ Sessions Retired (1)"


def test_sessions_keyboard_counts_retired_sessions():
    kb = sessions_keyboard(
        [
            Session("dbd65fb7", "a", "", Activity.RETIRED),
            Session("ab12cd34", "b", "", Activity.RETIRED),
        ]
    )
    assert kb.inline_keyboard[0][0].text == "⏸️ Sessions Retired (2)"


def test_sessions_keyboard_hides_retired_button_when_none_are():
    kb = sessions_keyboard([Session("dbd65fb7", "one", "", Activity.IDLE)])
    data = [b.callback_data for row in kb.inline_keyboard for b in row]
    assert "claude.retired|" not in data


def test_retired_keyboard_offers_resume_per_session_and_back():
    kb = retired_keyboard(
        [
            Session("dbd65fb7", "one", "", Activity.RETIRED),
            Session("ab12cd34", "two", "", Activity.RETIRED),
        ]
    )
    data = [[b.callback_data for b in row] for row in kb.inline_keyboard]
    assert data == [
        ["claude.resume|dbd65fb7"],
        ["claude.resume|ab12cd34"],
        ["claude.list|"],
    ]
    assert kb.inline_keyboard[0][0].text == "▶️ one"
    assert kb.inline_keyboard[-1][0].text == "⬅️ Back"


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

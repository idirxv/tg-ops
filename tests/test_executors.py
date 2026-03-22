"""Tests for bot/commands/executors.py."""

import shlex
from unittest.mock import AsyncMock

import pytest

from tg_ops.bot.commands.executors import ShellService


@pytest.fixture
def shell():
    return ShellService()


async def test_execute_failure_returns_nonzero_rc(shell):
    rc, stdout, stderr = await shell.execute("false")
    assert rc != 0
    assert stdout == ""


async def test_execute_oserror_returns_sentinel(shell, mocker):
    mocker.patch("asyncio.create_subprocess_shell", side_effect=OSError("no shell"))
    rc, stdout, stderr = await shell.execute("anything")
    assert rc == -1
    assert stdout == ""
    assert "no shell" in stderr


@pytest.mark.parametrize("ret_rc,expected", [(0, True), (1, False)])
async def test_is_service_active_maps_rc_to_bool(shell, mocker, ret_rc, expected):
    mocker.patch.object(shell, "execute", new=AsyncMock(return_value=(ret_rc, "", "")))
    result = await shell.is_service_active("myservice")
    assert result is expected


async def test_is_service_active_quotes_service_name(shell, mocker):
    mock_execute = AsyncMock(return_value=(0, "", ""))
    mocker.patch.object(shell, "execute", new=mock_execute)
    bad_name = "bad;name $(evil)"
    await shell.is_service_active(bad_name)
    called_command = mock_execute.call_args[0][0]
    assert shlex.quote(bad_name) in called_command

"""Tests for bot/commands/services.py."""

import re
from unittest.mock import AsyncMock, MagicMock

import pytest
from docker.errors import DockerException

from tg_ops.bot.commands.executors import ShellService
from tg_ops.bot.commands.services import DockerManager, SystemService
from tg_ops.config import Config


@pytest.fixture
def shell():
    return ShellService()


@pytest.fixture
def cfg_with_services():
    return Config(
        bot_token="tok",
        webhook_url="https://x.com",
        monitored_services=["svc-a", "svc-b"],
    )


# --- SystemService ---


async def test_system_snapshot_mixed_service_statuses(shell, cfg_with_services, mocker):
    mocker.patch("psutil.cpu_percent", return_value=10.0)
    mem = MagicMock(used=1 * 1024**3, total=8 * 1024**3, percent=12.5)
    mocker.patch("psutil.virtual_memory", return_value=mem)
    mocker.patch.object(
        shell, "is_service_active", new=AsyncMock(side_effect=[True, False])
    )

    svc = SystemService(shell, cfg_with_services)
    snap = await svc.get_system_snapshot()

    assert snap.services == {"svc-a": True, "svc-b": False}


async def test_system_snapshot_disk_format(shell, tmp_path, mocker):
    mocker.patch("psutil.cpu_percent", return_value=0.0)
    mem = MagicMock(used=0, total=1, percent=0.0)
    mocker.patch("psutil.virtual_memory", return_value=mem)
    disk = MagicMock(used=10 * 1024**3, total=100 * 1024**3, percent=10.0)
    mocker.patch("psutil.disk_usage", return_value=disk)

    cfg = Config(
        bot_token="tok",
        webhook_url="https://x.com",
        monitored_disks=[str(tmp_path)],
    )
    svc = SystemService(shell, cfg)
    snap = await svc.get_system_snapshot()

    assert len(snap.disks) == 1
    assert re.match(r".+ : \d+\.\d+/\d+\.\d+ Go \(\d+(\.\d+)?%\)", snap.disks[0])


# --- DockerManager ---


async def test_perform_action_calls_correct_compose_command(shell, tmp_path, mocker):
    mocker.patch("tg_ops.bot.commands.services.docker.from_env")
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.touch()

    cfg = Config(
        bot_token="tok",
        webhook_url="https://x.com",
        monitored_containers={"mybox": str(compose_file)},
    )
    mock_execute = AsyncMock(return_value=(0, "", ""))
    mocker.patch.object(shell, "execute", new=mock_execute)

    manager = DockerManager(shell, cfg)
    result = await manager.perform_action("restart", "mybox")

    assert result is True
    mock_execute.assert_called_once_with(f"docker compose -f {compose_file} restart")


async def test_perform_action_missing_compose_path_returns_false(shell, mocker):
    mocker.patch("tg_ops.bot.commands.services.docker.from_env")
    mock_execute = AsyncMock(return_value=(0, "", ""))
    mocker.patch.object(shell, "execute", new=mock_execute)

    cfg = Config(bot_token="tok", webhook_url="https://x.com")
    manager = DockerManager(shell, cfg)
    result = await manager.perform_action("restart", "unknown")

    assert result is False
    mock_execute.assert_not_called()


async def test_perform_action_nonzero_rc_returns_false(shell, tmp_path, mocker):
    mocker.patch("tg_ops.bot.commands.services.docker.from_env")
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.touch()

    cfg = Config(
        bot_token="tok",
        webhook_url="https://x.com",
        monitored_containers={"mybox": str(compose_file)},
    )
    mocker.patch.object(shell, "execute", new=AsyncMock(return_value=(1, "", "error")))

    manager = DockerManager(shell, cfg)
    result = await manager.perform_action("stop", "mybox")

    assert result is False


async def test_docker_init_failure_get_active_containers_returns_empty(shell, mocker):
    mocker.patch(
        "tg_ops.bot.commands.services.docker.from_env",
        side_effect=DockerException("no docker"),
    )
    cfg = Config(bot_token="tok", webhook_url="https://x.com")
    manager = DockerManager(shell, cfg)

    assert manager.client is None
    result = await manager.get_active_containers()
    assert result == []

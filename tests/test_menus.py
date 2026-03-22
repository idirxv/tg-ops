"""Tests for bot/ui/menus.py."""

import pytest

from tg_ops.bot.ui.menus import MenuBuilder
from tg_ops.config import Config


def all_callbacks(markup):
    return [btn.callback_data for row in markup.inline_keyboard for btn in row]


def test_container_actions_menu_running_has_stop_and_restart_not_start():
    markup = MenuBuilder.container_actions_menu("mybox", is_running=True)
    callbacks = all_callbacks(markup)
    assert any("restart" in c for c in callbacks)
    assert any("stop" in c for c in callbacks)
    assert not any("start" in c and "restart" not in c for c in callbacks)


def test_container_actions_menu_stopped_has_start_not_stop_or_restart():
    markup = MenuBuilder.container_actions_menu("mybox", is_running=False)
    callbacks = all_callbacks(markup)
    assert any("start" in c for c in callbacks)
    assert not any("stop" in c for c in callbacks)
    assert not any("restart" in c for c in callbacks)


def test_main_docker_menu_empty_containers_has_only_close():
    cfg = Config(bot_token="tok", webhook_url="https://x.com", monitored_containers={})
    markup = MenuBuilder.main_docker_menu(active_containers=[], cfg=cfg)
    callbacks = all_callbacks(markup)
    assert callbacks == ["close_menu"]

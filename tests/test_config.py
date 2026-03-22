"""Tests for config.py."""

import pytest

from tg_ops.config import Config, ConfigError


def write_toml(path, content: str):
    path.write_text(content, encoding="utf-8")
    return path


def test_missing_bot_token_raises(tmp_path):
    cfg = write_toml(tmp_path / "config.toml", 'webhook_url = "https://example.com"\n')
    with pytest.raises(ConfigError, match="bot_token"):
        Config.load(cfg)


def test_missing_webhook_url_raises(tmp_path):
    cfg = write_toml(tmp_path / "config.toml", 'bot_token = "tok"\n')
    with pytest.raises(ConfigError, match="webhook_url"):
        Config.load(cfg)


def test_wrong_port_type_raises(tmp_path):
    cfg = write_toml(
        tmp_path / "config.toml",
        'bot_token = "tok"\nwebhook_url = "https://x.com"\nport = "abc"\n',
    )
    with pytest.raises(ConfigError):
        Config.load(cfg)


def test_file_not_found_creates_sample_and_raises(tmp_path):
    missing = tmp_path / "missing.toml"
    with pytest.raises(ConfigError, match="not found"):
        Config.load(missing)
    assert missing.exists(), "sample config should be created"


def test_create_sample_sets_restrictive_permissions(tmp_path):
    path = tmp_path / "sample.toml"
    Config._create_sample(path)
    assert path.stat().st_mode & 0o777 == 0o600

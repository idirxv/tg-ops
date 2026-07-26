import pytest

from bot.config import Config, ConfigError, Webhook


def test_valid_config_parses(base_env):
    cfg = Config.from_env(base_env)
    assert cfg.telegram_bot_token == "123:abc"
    assert cfg.dockhand_url == "http://dockhand:3000"
    assert cfg.allowed_chat_ids == frozenset({111, -222})
    assert cfg.allowed_stacks == ("media", "vpn")
    assert cfg.dockhand_env == "1"
    assert cfg.log_level == "INFO"


def test_missing_vars_all_listed():
    with pytest.raises(ConfigError) as exc:
        Config.from_env({})
    msg = str(exc.value)
    assert "TELEGRAM_BOT_TOKEN" in msg
    assert "ALLOWED_STACKS" in msg
    assert "DOCKHAND_ENV" in msg


def test_non_numeric_dockhand_env_rejected(base_env):
    """Dockhand matches ?env= against the environment id; a name silently
    returns an empty stack list."""
    with pytest.raises(ConfigError, match="DOCKHAND_ENV"):
        Config.from_env(base_env | {"DOCKHAND_ENV": "homeserver"})


def test_non_integer_chat_id_rejected(base_env):
    with pytest.raises(ConfigError, match="ALLOWED_CHAT_IDS"):
        Config.from_env(base_env | {"ALLOWED_CHAT_IDS": "111,abc"})


def test_stack_name_with_pipe_rejected(base_env):
    with pytest.raises(ConfigError, match=r"\|"):
        Config.from_env(base_env | {"ALLOWED_STACKS": "bad|name"})


def test_stack_name_too_long_rejected(base_env):
    with pytest.raises(ConfigError, match="too long"):
        Config.from_env(base_env | {"ALLOWED_STACKS": "x" * 56})


def test_duplicate_stacks_deduped_order_kept(base_env):
    cfg = Config.from_env(base_env | {"ALLOWED_STACKS": "media,vpn,media"})
    assert cfg.allowed_stacks == ("media", "vpn")


def test_optional_vars(base_env):
    cfg = Config.from_env(base_env | {"DOCKHAND_ENV": "2", "LOG_LEVEL": "debug"})
    assert cfg.dockhand_env == "2"
    assert cfg.log_level == "DEBUG"


def test_default_mode_is_polling(base_env):
    assert Config.from_env(base_env).webhook is None


def test_webhook_settings_ignored_in_polling_mode(base_env):
    cfg = Config.from_env(
        base_env | {"WEBHOOK_URL": "https://x.example.com/t", "WEBHOOK_SECRET": "s"}
    )
    assert cfg.webhook is None


def test_invalid_mode_rejected(base_env):
    with pytest.raises(ConfigError, match="BOT_MODE"):
        Config.from_env(base_env | {"BOT_MODE": "carrier-pigeon"})


def test_webhook_mode_parses(webhook_env):
    cfg = Config.from_env(webhook_env)
    assert cfg.webhook == Webhook(
        url="https://tgbot.example.com/telegram", secret="s3cret_-token", port=5555
    )
    assert cfg.webhook.path == "telegram"


def test_webhook_path_empty_when_no_path(webhook_env):
    cfg = Config.from_env(webhook_env | {"WEBHOOK_URL": "https://tgbot.example.com"})
    assert cfg.webhook.path == ""


def test_webhook_mode_requires_url(webhook_env):
    del webhook_env["WEBHOOK_URL"]
    with pytest.raises(ConfigError, match="WEBHOOK_URL"):
        Config.from_env(webhook_env)


def test_webhook_mode_requires_secret(webhook_env):
    del webhook_env["WEBHOOK_SECRET"]
    with pytest.raises(ConfigError, match="WEBHOOK_SECRET"):
        Config.from_env(webhook_env)


def test_webhook_url_must_be_https(webhook_env):
    with pytest.raises(ConfigError, match="https"):
        Config.from_env(webhook_env | {"WEBHOOK_URL": "http://tgbot.example.com/t"})


def test_webhook_secret_charset_enforced(webhook_env):
    with pytest.raises(ConfigError, match="WEBHOOK_SECRET"):
        Config.from_env(webhook_env | {"WEBHOOK_SECRET": "bad secret!"})


def test_webhook_port_parsed(webhook_env):
    assert Config.from_env(webhook_env | {"WEBHOOK_PORT": "9000"}).webhook.port == 9000


@pytest.mark.parametrize("port", ["not-a-port", "70000", "0"])
def test_webhook_port_rejected(webhook_env, port):
    with pytest.raises(ConfigError, match="WEBHOOK_PORT"):
        Config.from_env(webhook_env | {"WEBHOOK_PORT": port})

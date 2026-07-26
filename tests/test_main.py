from unittest.mock import MagicMock

from telegram.ext import CallbackQueryHandler, CommandHandler, TypeHandler

from bot.main import build_application


def test_build_application_wires_everything(config):
    app = build_application(config, MagicMock())
    assert app.bot_data["config"] is config
    # auth gate runs first, in its own group before all others
    assert min(app.handlers) == -1
    assert isinstance(app.handlers[-1][0], TypeHandler)
    default_group = [type(h) for h in app.handlers[0]]
    assert CommandHandler in default_group
    assert CallbackQueryHandler in default_group

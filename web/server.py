"""Expose two routes: / (health check) and /webhook (Telegram endpoint)."""

from __future__ import annotations

import asyncio
import logging
from typing import Final

from flask import Flask, Response, request
from telegram import Update
from telegram.ext import Application

log = logging.getLogger(__name__)


def create_server(application: Application, *, loop: asyncio.AbstractEventLoop) -> Flask:
    """Build and configure the Flask object (without running it)."""
    app: Final = Flask(__name__)

    @app.get("/", endpoint="health")
    def health() -> tuple[str, int]:
        return "OK", 200

    @app.post("/webhook", endpoint="telegram_webhook")  # type: ignore[return-value]
    def webhook() -> Response:
        if request.headers.get("content-type") != "application/json":
            return Response("Unsupported Media Type", status=415)

        update = Update.de_json(request.get_json(force=True), application.bot)
        asyncio.run_coroutine_threadsafe(application.process_update(update), loop)
        return Response("OK", status=200)

    return app

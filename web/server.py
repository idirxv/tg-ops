"""Expose two routes and provide a controllable HTTP server for webhooks."""

from __future__ import annotations

import asyncio
import logging
import threading
from collections import OrderedDict
from typing import Final, Optional

from flask import Flask, Response, request
from telegram import Update
from telegram.ext import Application
from werkzeug.serving import make_server

log = logging.getLogger(__name__)


class WebServer:
    """A thin wrapper around Werkzeug's WSGI server to allow clean shutdown."""

    def __init__(self, app: Flask, *, host: str, port: int) -> None:
        self._app = app
        self._host = host
        self._port = port
        self._server = make_server(host, port, app, threaded=True)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    def start(self) -> None:
        log.info("HTTP server starting on %s:%s", self._host, self._port)
        self._thread.start()

    def stop(self) -> None:
        log.info("HTTP server shutting down…")
        try:
            self._server.shutdown()
        finally:
            self._thread.join(timeout=5)


def create_server(
    application: Application,
    *,
    loop: asyncio.AbstractEventLoop,
    host: str = "0.0.0.0",
    port: int = 5000,
    secret_token: Optional[str] = None,
) -> WebServer:
    """Build and return a controllable HTTP server wrapping a Flask app.

    - GET / → health check
    - POST /webhook → Telegram webhook endpoint
    """
    app: Final = Flask(__name__)

    # Simple in-memory idempotence cache (oldest-first eviction). Prevents
    # reprocessing of duplicate webhook deliveries within the process lifetime.
    seen_updates: OrderedDict[int, None] = OrderedDict()
    seen_max: Final[int] = 1024
    seen_lock = threading.Lock()

    @app.get("/", endpoint="health")
    def health() -> tuple[str, int]:
        return "OK", 200

    @app.post("/webhook", endpoint="telegram_webhook")  # type: ignore[return-value]
    def webhook() -> Response:
        if not request.is_json:
            return Response("Unsupported Media Type", status=415)

        if secret_token:
            provided = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
            if provided != secret_token:
                log.warning("Webhook rejected: invalid secret token")
                return Response("Forbidden", status=403)

        data = request.get_json(silent=True) or {}
        if not isinstance(data, dict):
            return Response("Bad Request", status=400)

        update_id = data.get("update_id")

        # Basic idempotence: drop duplicates by update_id.
        if isinstance(update_id, int):
            with seen_lock:
                if update_id in seen_updates:
                    # Move to end to reflect recent access and drop duplicate
                    seen_updates.move_to_end(update_id)
                    log.debug("Duplicate update %s ignored", update_id)
                    return Response("OK", status=200)
                seen_updates[update_id] = None
                if len(seen_updates) > seen_max:
                    seen_updates.popitem(last=False)

        update = Update.de_json(data, application.bot)
        asyncio.run_coroutine_threadsafe(application.process_update(update), loop)
        return Response("OK", status=200)

    return WebServer(app, host=host, port=port)

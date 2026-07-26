"""Thin blocking client for the Dockhand REST API.

Callers in async code must wrap calls in ``asyncio.to_thread``.
"""
from __future__ import annotations

import logging
from urllib.parse import quote

import requests

log = logging.getLogger(__name__)


class DockhandError(Exception):
    """A Dockhand API call failed."""


class DockhandClient:
    # (connect, read) timeouts: listing is quick; actions may pull images.
    LIST_TIMEOUT = (5, 15)
    ACTION_TIMEOUT = (5, 180)

    def __init__(self, base_url: str, token: str, env: str | None = None):
        self._base = base_url.rstrip("/")
        self._env = env
        self._session = requests.Session()
        self._session.headers["Authorization"] = f"Bearer {token}"
        self._session.headers["Accept"] = "application/json"

    def list_stacks(self) -> list[dict]:
        resp = self._request("GET", "/api/stacks", self.LIST_TIMEOUT)
        try:
            return resp.json()
        except ValueError as exc:
            raise DockhandError("Dockhand returned invalid JSON") from exc

    def stack_action(self, name: str, action: str) -> None:
        """Run "start", "stop" or "restart" on a stack.

        The body is never read: only the status code carries the outcome,
        and Dockhand may answer with no body at all.
        """
        self._request(
            "POST",
            f"/api/stacks/{quote(name, safe='')}/{action}",
            self.ACTION_TIMEOUT,
        )

    def _request(
        self, method: str, path: str, timeout: tuple[int, int]
    ) -> requests.Response:
        url = f"{self._base}{path}"
        params = {"env": self._env} if self._env else None
        try:
            resp = self._session.request(method, url, params=params, timeout=timeout)
        except requests.RequestException as exc:
            log.error("%s %s failed: %s", method, url, exc)
            raise DockhandError(
                f"Dockhand unreachable ({exc.__class__.__name__})"
            ) from exc
        if resp.status_code == 401:
            raise DockhandError("Dockhand rejected the API token (401)")
        if not resp.ok:
            log.error(
                "%s %s -> HTTP %s: %s", method, url, resp.status_code, resp.text[:200]
            )
            raise DockhandError(f"Dockhand returned HTTP {resp.status_code}")
        return resp

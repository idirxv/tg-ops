"""Thin blocking client for the Claude Host control service.

Callers in async code must wrap calls in ``asyncio.to_thread``.
"""
from __future__ import annotations

import logging
from typing import Any
from urllib.parse import quote

import requests

log = logging.getLogger(__name__)


class ClaudeHostError(Exception):
    """A control service call failed."""


class ClaudeHostTimeout(ClaudeHostError):
    """The control service accepted the request but did not answer in time.

    Unlike a connection failure, the operation may still be running.
    """


class ClaudeHostClient:
    # (connect, read) timeouts: opening waits on `claude --bg`, which the
    # service itself gives up on after 60s.
    LIST_TIMEOUT = (5, 15)
    OPEN_TIMEOUT = (5, 75)
    CLOSE_TIMEOUT = (5, 45)
    # Resuming waits on `claude respawn`, which the service gives up on after 60s.
    RESUME_TIMEOUT = (5, 75)
    # Checking runs `claude --version` and a release lookup capped at 10s;
    # updating waits on `claude update`, which the service gives up on after 150s.
    VERSION_TIMEOUT = (5, 30)
    UPDATE_TIMEOUT = (5, 180)

    def __init__(self, base_url: str, token: str):
        self._base = base_url.rstrip("/")
        self._session = requests.Session()
        self._session.headers["Authorization"] = f"Bearer {token}"
        self._session.headers["Accept"] = "application/json"

    def list_sessions(self) -> Any:
        return self._json(self._request("GET", "/sessions", self.LIST_TIMEOUT))

    def list_folders(self) -> list[str]:
        payload = self._json(self._request("GET", "/folders", self.LIST_TIMEOUT))
        folders = payload.get("folders") if isinstance(payload, dict) else None
        if not isinstance(folders, list) or not all(
            isinstance(f, str) for f in folders
        ):
            raise ClaudeHostError("Claude Host returned an unexpected folder list")
        return folders

    def open_session(self, folder: str = "") -> None:
        """Open a session in ``folder`` (empty for the workspace root)."""
        self._request("POST", "/sessions", self.OPEN_TIMEOUT, {"folder": folder})

    def close_session(self, session_id: str) -> None:
        self._request(
            "POST", f"/sessions/{quote(session_id, safe='')}/stop", self.CLOSE_TIMEOUT
        )

    def resume_session(self, session_id: str) -> None:
        """Restart the process of a Retired session."""
        self._request(
            "POST",
            f"/sessions/{quote(session_id, safe='')}/resume",
            self.RESUME_TIMEOUT,
        )

    def version(self) -> Any:
        return self._json(self._request("GET", "/version", self.VERSION_TIMEOUT))

    def update(self) -> Any:
        """Update Claude Code to the newest release on the host's channel."""
        return self._json(self._request("POST", "/update", self.UPDATE_TIMEOUT))

    @staticmethod
    def _json(resp: requests.Response) -> Any:
        try:
            return resp.json()
        except ValueError as exc:
            raise ClaudeHostError("Claude Host returned invalid JSON") from exc

    def _request(
        self,
        method: str,
        path: str,
        timeout: tuple[int, int],
        body: dict | None = None,
    ) -> requests.Response:
        url = f"{self._base}{path}"
        try:
            resp = self._session.request(method, url, json=body, timeout=timeout)
        except requests.ReadTimeout as exc:
            log.error("%s %s timed out after %ss", method, url, timeout[1])
            raise ClaudeHostTimeout(
                f"Claude Host did not answer within {timeout[1]}s"
            ) from exc
        except requests.RequestException as exc:
            log.error("%s %s failed: %s", method, url, exc)
            raise ClaudeHostError(
                f"Claude Host unreachable ({exc.__class__.__name__})"
            ) from exc
        if resp.status_code == 401:
            raise ClaudeHostError("Claude Host rejected the control token (401)")
        if not resp.ok:
            log.error(
                "%s %s -> HTTP %s: %s", method, url, resp.status_code, resp.text[:200]
            )
            raise ClaudeHostError(_error_message(resp))
        return resp


def _error_message(resp: requests.Response) -> str:
    """The service's own explanation ("Claude is not logged in", ...), if any."""
    try:
        message = resp.json().get("error")
    except (ValueError, AttributeError):
        message = None
    if isinstance(message, str) and message:
        return message[:200]
    return f"Claude Host returned HTTP {resp.status_code}"

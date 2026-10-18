"""Domain model: Claude Sessions parsed from the control service's payload."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

# What `claude --bg` calls a session's short id; also the only thing the
# control service will pass to `claude stop`.
SESSION_ID = re.compile(r"[0-9a-f]{8}")


@dataclass(frozen=True)
class Session:
    id: str
    name: str
    # Relative to the workspace; empty for the workspace root.
    folder: str
    busy: bool


def parse_sessions(payload: Any) -> tuple[bool, list[Session]]:
    """Return (claude is logged in, sessions)."""
    if not isinstance(payload, dict) or not isinstance(payload.get("sessions"), list):
        raise ValueError("unexpected /sessions payload")

    sessions = [
        Session(
            id=entry["id"],
            name=str(entry.get("name") or entry["id"]),
            folder=str(entry.get("folder") or ""),
            busy=entry.get("status") == "busy",
        )
        for entry in payload["sessions"]
        if isinstance(entry, dict)
        and isinstance(entry.get("id"), str)
        and SESSION_ID.fullmatch(entry["id"])
    ]
    return payload.get("logged_in") is True, sessions

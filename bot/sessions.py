"""Domain model: Claude Sessions parsed from the control service's payload."""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

# What `claude --bg` calls a session's short id; also the only thing the
# control service will pass to `claude stop`.
SESSION_ID = re.compile(r"[0-9a-f]{8}")


class Activity(Enum):
    BUSY = "busy"  # working on a turn
    IDLE = "idle"  # running, waiting for its user
    # The Claude Host stopped its process on its own (Claude Code retires
    # background sessions waiting on input under memory pressure). The
    # conversation is kept, but `claude stop` no longer works on it.
    RETIRED = "retired"


@dataclass(frozen=True)
class Session:
    id: str
    name: str
    # Relative to the workspace; empty for the workspace root.
    folder: str
    activity: Activity


def _activity(status: Any) -> Activity:
    # `claude agents --json` gives a status only to sessions with a live process.
    if status == "busy":
        return Activity.BUSY
    if status is None:
        return Activity.RETIRED
    return Activity.IDLE


def parse_sessions(payload: Any) -> tuple[bool, list[Session]]:
    """Return (claude is logged in, sessions)."""
    if not isinstance(payload, dict) or not isinstance(payload.get("sessions"), list):
        raise ValueError("unexpected /sessions payload")

    sessions = [
        Session(
            id=entry["id"],
            name=str(entry.get("name") or entry["id"]),
            folder=str(entry.get("folder") or ""),
            activity=_activity(entry.get("status")),
        )
        for entry in payload["sessions"]
        if isinstance(entry, dict)
        and isinstance(entry.get("id"), str)
        and SESSION_ID.fullmatch(entry["id"])
    ]
    return payload.get("logged_in") is True, sessions

"""Domain model: stack status derived from Dockhand's /api/stacks payload."""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Any


class StackStatus(Enum):
    RUNNING = "running"
    STOPPED = "stopped"
    PARTIAL = "partially running"


STATUS_DOT = {
    StackStatus.RUNNING: "🟢",
    StackStatus.STOPPED: "🔴",
    StackStatus.PARTIAL: "🟡",
}


@dataclass(frozen=True)
class Container:
    name: str
    state: str


@dataclass(frozen=True)
class Stack:
    name: str
    status: StackStatus
    containers: tuple[Container, ...] = ()


def compute_status(
    container_states: Sequence[str], fallback: str | None = None
) -> StackStatus:
    if not container_states:
        return StackStatus.RUNNING if fallback == "running" else StackStatus.STOPPED
    running = sum(1 for state in container_states if state == "running")
    if running == 0:
        return StackStatus.STOPPED
    if running == len(container_states):
        return StackStatus.RUNNING
    return StackStatus.PARTIAL


def parse_stacks(payload: Any, allowed_stacks: Sequence[str]) -> list[Stack]:
    if not isinstance(payload, list):
        raise ValueError("unexpected /api/stacks payload (not a list)")

    by_name: dict[str, dict] = {}
    for entry in payload:
        if isinstance(entry, dict) and isinstance(entry.get("name"), str):
            by_name[entry["name"]] = entry

    stacks: list[Stack] = []
    for name in allowed_stacks:
        entry = by_name.get(name)
        if entry is None:
            continue
        # Dockhand puts container objects in "containerDetails"; the
        # "containers" key holds bare container ids.
        containers = tuple(
            Container(
                name=str(c.get("name", "?")),
                state=str(c.get("state", "unknown")),
            )
            for c in entry.get("containerDetails") or ()
            if isinstance(c, dict)
        )
        status = compute_status([c.state for c in containers], entry.get("status"))
        stacks.append(Stack(name=name, status=status, containers=containers))
    return stacks

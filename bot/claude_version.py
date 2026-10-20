"""Domain model: the Claude Host's Installed version and Updates, parsed from
the control service's ``/version`` and ``/update`` payloads."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

_VERSION = re.compile(r"(\d+)\.(\d+)\.(\d+)(?:-[0-9A-Za-z.-]+)?")
_CHANNEL = re.compile(r"[a-z]+")


def _key(version: str) -> tuple[int, ...]:
    match = _VERSION.fullmatch(version)
    if not match:
        raise ValueError(f"not a version: {version!r}")
    return tuple(int(part) for part in match.groups())


@dataclass(frozen=True)
class VersionCheck:
    installed: str
    # Newest release on the host's update channel; None when the lookup failed.
    latest: str | None
    channel: str

    @property
    def update_available(self) -> bool:
        # Compared, not just unequal: the stable channel can lag behind.
        return self.latest is not None and _key(self.latest) > _key(self.installed)


@dataclass(frozen=True)
class UpdateResult:
    before: str
    after: str

    @property
    def changed(self) -> bool:
        return self.before != self.after


def _version(payload: dict, key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not _VERSION.fullmatch(value):
        raise ValueError(f"unexpected {key!r} version: {value!r}")
    return value


def parse_version_check(payload: Any) -> VersionCheck:
    if not isinstance(payload, dict) or "latest" not in payload:
        raise ValueError("unexpected /version payload")
    channel = payload.get("channel")
    if not isinstance(channel, str) or not _CHANNEL.fullmatch(channel):
        raise ValueError(f"unexpected update channel: {channel!r}")
    return VersionCheck(
        installed=_version(payload, "installed"),
        latest=None if payload["latest"] is None else _version(payload, "latest"),
        channel=channel,
    )


def parse_update(payload: Any) -> UpdateResult:
    if not isinstance(payload, dict):
        raise ValueError("unexpected /update payload")
    return UpdateResult(_version(payload, "before"), _version(payload, "after"))

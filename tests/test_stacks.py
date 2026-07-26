import pytest

from bot.stacks import Container, StackStatus, compute_status, parse_stacks


def test_all_running():
    assert compute_status(["running", "running"]) is StackStatus.RUNNING


def test_none_running():
    assert compute_status(["exited", "created"]) is StackStatus.STOPPED


def test_mixed_is_partial():
    assert compute_status(["running", "exited"]) is StackStatus.PARTIAL


def test_no_containers_uses_fallback():
    assert compute_status([], fallback="running") is StackStatus.RUNNING
    assert compute_status([], fallback="stopped") is StackStatus.STOPPED
    assert compute_status([]) is StackStatus.STOPPED


# Shape of a real Dockhand /api/stacks entry: "containers" holds container
# *ids*, the dicts live in "containerDetails".
PAYLOAD = [
    {
        "name": "media",
        "status": "running",
        "containers": ["7a06218096"],
        "containerDetails": [
            {
                "id": "7a06218096",
                "name": "media-jellyfin-1",
                "service": "jellyfin",
                "state": "running",
            }
        ],
    },
    {"name": "vpn", "status": "stopped", "containers": [], "containerDetails": []},
    {"name": "secret", "status": "running", "containers": [], "containerDetails": []},
]


def test_parse_filters_and_orders_by_allowlist():
    stacks = parse_stacks(PAYLOAD, ["vpn", "media"])
    assert [s.name for s in stacks] == ["vpn", "media"]
    assert stacks[0].status is StackStatus.STOPPED
    assert stacks[1].status is StackStatus.RUNNING
    assert stacks[1].containers == (Container("media-jellyfin-1", "running"),)


def test_parse_skips_allowed_stack_missing_from_api():
    assert parse_stacks(PAYLOAD, ["nope"]) == []


def test_parse_rejects_non_list_payload():
    with pytest.raises(ValueError):
        parse_stacks({"error": "boom"}, ["media"])


def test_parse_tolerates_malformed_entries():
    payload = ["junk", {"no_name": 1}, {"name": "media", "containerDetails": None}]
    stacks = parse_stacks(payload, ["media"])
    assert [s.name for s in stacks] == ["media"]
    assert stacks[0].status is StackStatus.STOPPED


def test_parse_ignores_container_id_strings():
    """"containers" is a list of id strings, never container objects."""
    payload = [{"name": "media", "status": "running", "containers": ["7a06218096"]}]
    stacks = parse_stacks(payload, ["media"])
    assert stacks[0].containers == ()
    assert stacks[0].status is StackStatus.RUNNING


def test_parse_reads_partial_state_from_container_details():
    payload = [
        {
            "name": "media",
            "status": "running",
            "containers": ["a", "b"],
            "containerDetails": [
                {"name": "media-jellyfin-1", "state": "running"},
                {"name": "media-sonarr-1", "state": "exited"},
            ],
        }
    ]
    stacks = parse_stacks(payload, ["media"])
    assert stacks[0].status is StackStatus.PARTIAL
    assert [c.name for c in stacks[0].containers] == [
        "media-jellyfin-1",
        "media-sonarr-1",
    ]

import pytest

from bot.claude_version import (
    UpdateResult,
    VersionCheck,
    parse_update,
    parse_version_check,
)


def test_parse_version_check():
    check = parse_version_check(
        {"installed": "2.1.305", "latest": "2.1.306", "channel": "latest"}
    )
    assert check == VersionCheck("2.1.305", "2.1.306", "latest")
    assert check.update_available


def test_parse_version_check_without_latest():
    check = parse_version_check(
        {"installed": "2.1.305", "latest": None, "channel": "latest"}
    )
    assert check.latest is None
    assert not check.update_available


@pytest.mark.parametrize(
    ("installed", "latest", "available"),
    [
        ("2.1.305", "2.1.305", False),
        ("2.1.305", "2.1.306", True),
        ("2.1.99", "2.1.100", True),  # numeric, not string, order
        ("2.1.305", "2.1.304", False),  # the stable channel can lag behind
        ("2.9.0", "3.0.0", True),
    ],
)
def test_update_available_compares_versions_numerically(installed, latest, available):
    assert VersionCheck(installed, latest, "latest").update_available is available


@pytest.mark.parametrize(
    "payload",
    [
        None,
        [],
        {},
        {"installed": "2.1.305", "channel": "latest"},  # latest key missing
        {"installed": "<b>", "latest": None, "channel": "latest"},
        {"installed": "2.1.305", "latest": "x", "channel": "latest"},
        {"installed": "2.1.305", "latest": None, "channel": "<i>"},
    ],
)
def test_parse_version_check_rejects_unexpected_payload(payload):
    with pytest.raises(ValueError):
        parse_version_check(payload)


def test_parse_update():
    result = parse_update({"before": "2.1.305", "after": "2.1.306"})
    assert result == UpdateResult("2.1.305", "2.1.306")
    assert result.changed
    assert not parse_update({"before": "2.1.305", "after": "2.1.305"}).changed


@pytest.mark.parametrize("payload", [None, {}, {"before": "2.1.305", "after": 3}])
def test_parse_update_rejects_unexpected_payload(payload):
    with pytest.raises(ValueError):
        parse_update(payload)

import pytest

from bot.sessions import Activity, Session, parse_sessions


def _entry(**overrides):
    return {
        "id": "dbd65fb7",
        "name": "greeting exchange",
        "folder": "petuka-db",
        "status": "idle",
        "state": "blocked",
    } | overrides


def test_parse_maps_fields_and_login_state():
    logged_in, sessions = parse_sessions(
        {
            "logged_in": True,
            "sessions": [_entry(), _entry(id="ab12cd34", status="busy")],
        }
    )
    assert logged_in is True
    assert sessions == [
        Session("dbd65fb7", "greeting exchange", "petuka-db", Activity.IDLE),
        Session("ab12cd34", "greeting exchange", "petuka-db", Activity.BUSY),
    ]


def test_session_without_status_is_retired():
    # What `claude agents --json` lists for a background session whose
    # process the host stopped: no pid, no status, state still "blocked".
    _, [session] = parse_sessions({"sessions": [_entry(status=None)]})
    assert session.activity is Activity.RETIRED


def test_logged_out_unless_explicitly_true():
    assert parse_sessions({"sessions": []}) == (False, [])
    assert parse_sessions({"logged_in": "yes", "sessions": []}) == (False, [])


def test_missing_name_falls_back_to_id_and_folder_to_root():
    _, [session] = parse_sessions({"sessions": [_entry(name=None, folder=None)]})
    assert (session.name, session.folder) == ("dbd65fb7", "")


@pytest.mark.parametrize(
    "bad_id", ["--all", "DBD65FB7", "dbd65fb", "dbd65fb7;ls", 7, None]
)
def test_entries_without_a_valid_id_are_dropped(bad_id):
    _, sessions = parse_sessions({"sessions": [_entry(id=bad_id), "junk"]})
    assert sessions == []


@pytest.mark.parametrize("payload", [[], None, {}, {"sessions": "x"}])
def test_unexpected_payload_raises(payload):
    with pytest.raises(ValueError):
        parse_sessions(payload)

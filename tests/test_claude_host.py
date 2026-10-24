import json

import pytest
import requests
import responses
from urllib3.exceptions import (
    ConnectTimeoutError,
    MaxRetryError,
    NewConnectionError,
    ProtocolError,
)

from bot.claude_host import (
    ClaudeHostClient,
    ClaudeHostError,
    ClaudeHostStopped,
    ClaudeHostTimeout,
)

BASE = "http://claude-code:8080"


@pytest.fixture
def client():
    return ClaudeHostClient(BASE + "/", "ctl_token")


@responses.activate
def test_list_sessions_returns_payload_and_sends_bearer_token(client):
    responses.get(f"{BASE}/sessions", json={"logged_in": True, "sessions": []})
    assert client.list_sessions() == {"logged_in": True, "sessions": []}
    assert responses.calls[0].request.headers["Authorization"] == "Bearer ctl_token"


@responses.activate
def test_list_folders(client):
    responses.get(f"{BASE}/folders", json={"folders": ["alpha", "petuka-db"]})
    assert client.list_folders() == ["alpha", "petuka-db"]


@responses.activate
@pytest.mark.parametrize("body", [{}, {"folders": "x"}, {"folders": [1]}, []])
def test_list_folders_rejects_unexpected_payload(client, body):
    responses.get(f"{BASE}/folders", json=body)
    with pytest.raises(ClaudeHostError, match="unexpected folder list"):
        client.list_folders()


@responses.activate
def test_open_session_posts_the_folder(client):
    responses.post(f"{BASE}/sessions", json={"id": "ab12cd34"}, status=201)
    client.open_session("petuka-db")
    assert json.loads(responses.calls[0].request.body) == {"folder": "petuka-db"}


@responses.activate
def test_close_session_posts_to_stop(client):
    responses.post(f"{BASE}/sessions/dbd65fb7/stop", json={"ok": True})
    client.close_session("dbd65fb7")
    assert len(responses.calls) == 1


@responses.activate
def test_resume_session_posts_to_resume(client):
    responses.post(f"{BASE}/sessions/dbd65fb7/resume", json={"ok": True})
    client.resume_session("dbd65fb7")
    assert len(responses.calls) == 1


@responses.activate
def test_version_returns_payload(client):
    body = {"installed": "2.1.305", "latest": "2.1.306", "channel": "latest"}
    responses.get(f"{BASE}/version", json=body)
    assert client.version() == body


@responses.activate
def test_update_posts_and_returns_payload(client):
    responses.post(f"{BASE}/update", json={"before": "2.1.305", "after": "2.1.306"})
    assert client.update() == {"before": "2.1.305", "after": "2.1.306"}


@responses.activate
def test_service_error_message_is_surfaced(client):
    responses.post(
        f"{BASE}/sessions", json={"error": "Claude is not logged in"}, status=409
    )
    with pytest.raises(ClaudeHostError, match="Claude is not logged in"):
        client.open_session()


@responses.activate
def test_error_without_message_falls_back_to_status(client):
    responses.get(f"{BASE}/sessions", body="<html>", status=500)
    with pytest.raises(ClaudeHostError, match="HTTP 500"):
        client.list_sessions()


@responses.activate
def test_401_names_the_token(client):
    responses.get(f"{BASE}/sessions", json={"error": "unauthorized"}, status=401)
    with pytest.raises(ClaudeHostError, match="rejected the control token"):
        client.list_sessions()


@responses.activate
def test_invalid_json_raises(client):
    responses.get(f"{BASE}/sessions", body="nope")
    with pytest.raises(ClaudeHostError, match="invalid JSON"):
        client.list_sessions()


@responses.activate
def test_read_timeout_is_distinguished_from_unreachable(client):
    responses.post(f"{BASE}/sessions", body=requests.ReadTimeout())
    with pytest.raises(ClaudeHostTimeout):
        client.open_session()


def _refused():
    # The shape requests gives a refused connection.
    reason = NewConnectionError(None, "Connection refused to secret-host")
    return requests.ConnectionError(MaxRetryError(None, "/sessions", reason))


@responses.activate
def test_refused_connection_means_the_host_is_stopped(client):
    responses.get(f"{BASE}/sessions", body=_refused())
    with pytest.raises(ClaudeHostStopped) as exc:
        client.list_sessions()
    assert str(exc.value) == "Claude Host is stopped — start its stack from /docker"
    assert "secret-host" not in str(exc.value)


@responses.activate
def test_connection_dropped_mid_request_is_not_reported_as_stopped(client):
    # The host was reached, so the action failed: it is not stopped.
    dropped = requests.ConnectionError(
        ProtocolError("Connection aborted.", ConnectionResetError())
    )
    responses.post(f"{BASE}/update", body=dropped)
    with pytest.raises(ClaudeHostError, match=r"unreachable \(ConnectionError\)") as e:
        client.update()
    assert not isinstance(e.value, ClaudeHostStopped)


@responses.activate
def test_connect_timeout_is_not_reported_as_stopped(client):
    timeout = requests.ConnectTimeout(
        MaxRetryError(None, "/sessions", ConnectTimeoutError("secret-host"))
    )
    responses.get(f"{BASE}/sessions", body=timeout)
    with pytest.raises(ClaudeHostError, match=r"unreachable \(ConnectTimeout\)") as exc:
        client.list_sessions()
    assert not isinstance(exc.value, ClaudeHostStopped | ClaudeHostTimeout)
    assert "secret-host" not in str(exc.value)

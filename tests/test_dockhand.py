import pytest
import requests
import responses

from bot.dockhand import DockhandClient, DockhandError

BASE = "http://dockhand:3000"


@pytest.fixture
def client():
    return DockhandClient(BASE, "dh_test")


@responses.activate
def test_list_stacks_success_and_auth_header(client):
    responses.get(f"{BASE}/api/stacks", json=[{"name": "media"}])
    assert client.list_stacks() == [{"name": "media"}]
    assert responses.calls[0].request.headers["Authorization"] == "Bearer dh_test"


@responses.activate
def test_env_param_sent_when_configured():
    client = DockhandClient(BASE, "dh_test", env="prod")
    responses.get(f"{BASE}/api/stacks", json=[])
    client.list_stacks()
    assert "env=prod" in responses.calls[0].request.url


@responses.activate
def test_no_env_param_by_default(client):
    responses.get(f"{BASE}/api/stacks", json=[])
    client.list_stacks()
    assert "env=" not in responses.calls[0].request.url


@responses.activate
def test_actions_post_to_right_endpoints(client):
    for action in ("start", "stop", "restart"):
        responses.post(f"{BASE}/api/stacks/media/{action}", json={"success": True})
        client.stack_action("media", action)
    assert len(responses.calls) == 3


@responses.activate
def test_stack_name_is_url_quoted(client):
    responses.post(f"{BASE}/api/stacks/my%20stack/restart", json={"success": True})
    client.stack_action("my stack", "restart")


@responses.activate
def test_action_accepts_empty_body(client):
    """Only the status code carries the outcome; an empty 204 is success."""
    responses.post(f"{BASE}/api/stacks/media/stop", status=204, body="")
    client.stack_action("media", "stop")


@responses.activate
def test_401_raises_token_error(client):
    responses.get(f"{BASE}/api/stacks", status=401, json={})
    with pytest.raises(DockhandError, match="token"):
        client.list_stacks()


@responses.activate
def test_5xx_raises(client):
    responses.post(f"{BASE}/api/stacks/media/stop", status=500, json={})
    with pytest.raises(DockhandError, match="500"):
        client.stack_action("media", "stop")


@responses.activate
def test_connection_error_raises(client):
    responses.get(
        f"{BASE}/api/stacks", body=requests.exceptions.ConnectionError("boom")
    )
    with pytest.raises(DockhandError, match="unreachable"):
        client.list_stacks()


@responses.activate
def test_invalid_json_raises(client):
    responses.get(f"{BASE}/api/stacks", body="<html>login</html>")
    with pytest.raises(DockhandError, match="JSON"):
        client.list_stacks()

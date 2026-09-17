import json
import socket
import threading
import time
from contextlib import contextmanager
from dataclasses import asdict
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import uvicorn

from kbht_server.adapters.commands import CommandAdapter
from kbht_server.adapters.http import create_app
from kbht_server.db.uow import CommandExecutor
from pg_lab import ACCOUNT_IDS
from purchase_fixture import purchase


@contextmanager
def live_http(app):
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(16)
    server = uvicorn.Server(uvicorn.Config(app, log_level="critical", access_log=False))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 10
        while not server.started:
            assert thread.is_alive() and time.monotonic() < deadline, "HTTP listener did not start"
            time.sleep(0.01)
        yield f"http://127.0.0.1:{listener.getsockname()[1]}"
    finally:
        server.should_exit = True
        thread.join(10)
        listener.close()
        assert not thread.is_alive()


def post(base, envelope, headers=None):
    request = Request(base + "/v1/command", data=json.dumps(envelope).encode(),
                      headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urlopen(request, timeout=5) as response:
            return response.status, json.load(response)
    except HTTPError as response:
        return response.code, json.load(response)


def envelope_for(lab):
    command = lab.purchase_command(player_id=10001, cost_gem=10, reward_coin=300, key="http")
    envelope = json.loads(json.dumps(asdict(command), default=str))
    envelope.pop("account_id")
    return envelope


def test_forged_account_header_cannot_spend(pg_lab):
    adapter = CommandAdapter(CommandExecutor(pg_lab.engine, {"internal.purchase": purchase}), {"internal.purchase"})
    with live_http(create_app(adapter)) as base:
        status, result = post(base, envelope_for(pg_lab), {"X-Account-Id": str(ACCOUNT_IDS[10001])})
    assert status == 401
    assert pg_lab.wallet(10001, "gem") == 50


def test_authenticated_http_roundtrip_replay_and_bad_envelope(pg_lab):
    adapter = CommandAdapter(CommandExecutor(pg_lab.engine, {"internal.purchase": purchase}), {"internal.purchase"})
    def authenticate(token):
        return ACCOUNT_IDS[10001] if token == "test-only-session" else None
    app = create_app(adapter, authenticate=authenticate)
    envelope = envelope_for(pg_lab)
    with live_http(app) as base:
        assert post(base, envelope, {"Authorization": "Bearer invalid"})[0] == 401
        headers = {"Authorization": "Bearer test-only-session"}
        status, result = post(base, envelope, headers)
        assert status == 200
        assert result["result"] == {"gem": 40, "coin": 300}
        assert post(base, envelope, headers) == (status, result)
        for field, value in (("player_id", True), ("player_id", "10001"), ("account_id", str(ACCOUNT_IDS[10002]))):
            assert post(base, {**envelope, field: value}, headers)[0] == 422
    assert pg_lab.wallet(10001, "gem") == 40

def test_durable_session_http_revoke(pg_lab):
    from kbht_server.auth import SessionService
    sessions = SessionService(pg_lab.engine)
    token = sessions.issue(ACCOUNT_IDS[10001])
    adapter = CommandAdapter(CommandExecutor(pg_lab.engine, {"internal.purchase": purchase}), {"internal.purchase"})
    with live_http(create_app(adapter, authenticate=SessionService(pg_lab.engine).resolve)) as base:
        headers = {"Authorization": "Bearer " + token}
        envelope = envelope_for(pg_lab)
        assert post(base, envelope, headers)[0] == 200
        sessions.revoke(token)
        assert post(base, envelope, headers)[0] == 401
    assert pg_lab.wallet(10001, "gem") == 40

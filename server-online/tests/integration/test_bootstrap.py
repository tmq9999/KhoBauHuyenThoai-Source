"""Loopback auth/bootstrap contracts, with real PostgreSQL and HTTP sockets."""
import asyncio
import base64
import hashlib
import importlib
import json
import http.client
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import UUID
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest
from sqlalchemy import event, inspect, text

from kbht_server.auth import AccountService, SessionService
from kbht_server.db.migrations import check_invariants
from pg_lab import ACCOUNT_IDS, CONTENT_ID
from test_http_adapter import live_http
from test_fixed_boxes import box_lab, draft_boxes


def app(engine, **kwargs):
    from kbht_server.adapters import http
    # Behavioral RED: absent factory is asserted, not an import collection error.
    module = importlib.import_module('kbht_server.adapters.bootstrap') if importlib.util.find_spec('kbht_server.adapters.bootstrap') else http
    assert hasattr(module, 'create_bootstrap_app'), 'separate bootstrap HTTP boundary missing'
    return module.create_bootstrap_app(engine, **kwargs)


def request(base, path, method='GET', body=None, token=None, headers=None):
    data = json.dumps(body).encode() if body is not None else None
    header = {'Content-Type': 'application/json', **(headers or {})}
    if token:
        header['Authorization'] = 'Bearer ' + token
    req = Request(base + path, data=data, method=method, headers=header)
    try:
        response = urlopen(req, timeout=10)
    except HTTPError as error:
        response = error
    with response:
        raw = response.read()
        assert response.headers['Cache-Control'] == 'no-store'
        assert response.headers.get('Set-Cookie') is None
        return response.status, json.loads(raw) if raw else None


def credentials(login='bootstrap-user'):
    return {'login': login, 'password': 'test-only-password'}


def test_registration_uses_argon2_and_normalized_login(pg_engine):
    service = AccountService(pg_engine)
    account = service.register('  Alice  ', 'test-only-password')
    with pg_engine.connect() as connection:
        row = connection.execute(text('SELECT normalized_login,password_hash FROM accounts WHERE id=:id'), {'id': account}).one()
    assert row.normalized_login == 'alice'
    assert row.password_hash.startswith('$argon2id$')
    assert service.authenticate('ALICE', 'test-only-password') == account
    assert service.authenticate('alice', 'incorrect-password') is None


def test_scrypt_upgrade_only_after_valid_password_and_unknown_scheme_denied(pg_engine):
    service = AccountService(pg_engine)
    account = service.register('legacy-user', 'test-only-password')
    salt = b'0123456789abcdef'
    encoded = 'scrypt$' + base64.urlsafe_b64encode(salt).decode() + '$' + base64.urlsafe_b64encode(hashlib.scrypt(b'test-only-password', salt=salt, n=16384, r=8, p=1)).decode()
    for stored, valid in [(encoded.replace('scrypt$', 'unknown$'), False), ('scrypt$bad$bad', False), ('$argon2id$invalid', False), (encoded, True)]:
        with pg_engine.begin() as connection:
            connection.execute(text('UPDATE accounts SET password_hash=:hash WHERE id=:id'), {'hash': stored, 'id': account})
        assert service.authenticate('legacy-user', 'incorrect-password') is None
        with pg_engine.connect() as connection:
            assert connection.execute(text('SELECT password_hash FROM accounts WHERE id=:id'), {'id': account}).scalar_one() == stored
        assert service.authenticate('legacy-user', 'test-only-password') == (account if valid else None)
    with pg_engine.connect() as connection:
        assert connection.execute(text('SELECT password_hash FROM accounts WHERE id=:id'), {'id': account}).scalar_one().startswith('$argon2id$')


def test_locked_account_denies_password_and_existing_or_new_session(pg_engine):
    assert 'status' in {column['name'] for column in inspect(pg_engine).get_columns('accounts')}, 'account lock column missing'
    account = AccountService(pg_engine).register('locked-user', 'test-only-password')
    token = SessionService(pg_engine).issue(account)
    with pg_engine.begin() as connection:
        connection.execute(text("UPDATE accounts SET status='LOCKED' WHERE id=:id"), {'id': account})
    assert AccountService(pg_engine).authenticate('locked-user', 'test-only-password') is None
    assert SessionService(pg_engine).resolve(token) is None
    with pytest.raises(ValueError):
        SessionService(pg_engine).issue(account)


def test_http_accounts_login_rotation_list_and_revoke(pg_engine):
    with live_http(app(pg_engine)) as base:
        status, registered = request(base, '/v1/accounts', 'POST', credentials())
        assert status == 201 and UUID(registered['accountId'])
        assert request(base, '/v1/accounts', 'POST', credentials())[0] == 409
        assert request(base, '/v1/sessions', 'POST', {**credentials(), 'password': 'incorrect-password'})[0] == 401
        status, first = request(base, '/v1/sessions', 'POST', credentials())
        assert status == 200 and first['tokenType'] == 'Bearer' and first['expiresIn'] == 3600
        token = first['token']
        assert request(base, '/v1/players', token=token) == (200, {'players': [], 'nextAfter': None})
        _, second = request(base, '/v1/sessions', 'POST', credentials())
        assert request(base, '/v1/players', token=token)[0] == 401
        assert request(base, '/v1/sessions/current', 'DELETE', token=second['token'])[0] == 204
        assert request(base, '/v1/players', token=second['token'])[0] == 401
    with pg_engine.connect() as connection:
        assert connection.execute(text('SELECT count(*) FROM players')).scalar_one() == 0


@pytest.mark.parametrize('body', [None, [], {'login': 'abc', 'password': 'short'}, {**credentials(), 'accountId': 'forged'}, {'login': True, 'password': 'test-only-password'}])
def test_bad_credentials_are_redacted(pg_engine, body):
    with live_http(app(pg_engine)) as base:
        status, result = request(base, '/v1/accounts', 'POST', body)
    assert status == 422
    assert result['error'] == {'code': 'VALIDATION_ERROR', 'message': 'Invalid request', 'details': {}}
    assert 'test-only-password' not in json.dumps(result)


def test_browser_query_body_limits_and_pagination_validation(pg_engine):
    with live_http(app(pg_engine)) as base:
        assert request(base, '/v1/accounts', 'POST', credentials(), headers={'Origin': 'https://example.test'})[0] == 403
        assert request(base, '/v1/accounts?password=never-log', 'POST', credentials())[0] == 422
        assert request(base, '/v1/accounts', 'POST', {'login': 'x'*5000, 'password': 'test-only-password'})[0] == 413
        assert request(base, '/v1/accounts', 'POST', credentials(), headers={'Content-Type': 'text/plain'})[0] == 415
        account = AccountService(pg_engine).register('page-user', 'test-only-password')
        token = SessionService(pg_engine).issue(account)
        for query in ['limit=0', 'limit=101', 'limit=true', 'after=-1', 'after=9007199254740992', 'accountId=forged', 'limit=1&limit=2']:
            assert request(base, '/v1/players?'+query, token=token)[0] == 422


def test_bootstrap_owned_release_snapshot_and_real_pomelo_replay(box_lab):
    from test_pomelo_inventory import _running, _connect, _ws_frame, _handshake, _read_ws, _request, _player_envelope
    from kbht_server.adapters.pomelo_codec import HANDSHAKE_ACK, encode_frame, decode_frames
    lab = box_lab
    with live_http(app(lab.engine)) as base:
        _, registered = request(base, '/v1/accounts', 'POST', credentials())
        account = UUID(registered['accountId'])
        with lab.engine.begin() as connection:
            connection.execute(text('UPDATE players SET account_id=:account WHERE id=10001'), {'account': account})
        _, session = request(base, '/v1/sessions', 'POST', credentials())
        token = session['token']
        status, listing = request(base, '/v1/players?limit=1', token=token)
        assert status == 200 and [row['playerId'] for row in listing['players']] == [10001]
        assert request(base, '/v1/players?after=10001', token=token)[1]['players'] == []
        status, selected = request(base, '/v1/inventory/bootstrap', 'POST', {'playerId': 10001, 'serverId': 1}, token)
        assert status == 200
        assert selected['hello'] == {'protocolVersion': 1, 'capabilities': ['native-inventory-v1'], 'playerId': 10001, 'serverId': 1, 'contentVersionId': str(CONTENT_ID)}
        assert selected['inventoryUrl'] == 'ws://127.0.0.1:21002/inventory'
        assert selected['inventoryIdentity'] == 'postgres-v1' and selected['fullPlayerSnapshot'] is False
        assert selected['snapshot']['contentVersionId'] == str(CONTENT_ID)
        assert token not in json.dumps(selected)
        assert request(base, '/v1/inventory/bootstrap', 'POST', {'playerId': 10002, 'serverId': 1}, token)[0] == 403
        for body in [{'playerId': True, 'serverId': 1}, {'playerId': 10001, 'serverId': 1, 'accountId': str(account)}]:
            assert request(base, '/v1/inventory/bootstrap', 'POST', body, token)[0] == 422
    async def roundtrip():
        async with _running(lab) as server:
            reader, writer = await _connect(server)
            writer.write(_ws_frame(_handshake(token, selected['hello'])))
            await writer.drain()
            _, raw = await _read_ws(reader)
            assert json.loads(decode_frames(raw)[0][1])['code'] == 200
            writer.write(_ws_frame(encode_frame(HANDSHAKE_ACK, b'')))
            await writer.drain()
            envelope = _player_envelope(lab, 10001, key='bootstrap-box')
            first = await _request(reader, writer, 1, 'logic.playerHandler.useItem', envelope)
            assert first['code'] == 200
            assert await _request(reader, writer, 2, 'logic.playerHandler.useItem', envelope) == first
            writer.close()
            await writer.wait_closed()
            return UUID(envelope['command_id'])
    command_id = asyncio.run(roundtrip())
    assert lab.receipt_count(command_id) == 1
    assert lab.item_quantity(10001, 321) == 1 and lab.item_quantity(10001, 49902) == 6
    assert not any(check_invariants(lab.engine).values())


def test_cli_bootstrap_is_explicit_and_rejects_invalid_configuration():
    result = subprocess.run([sys.executable, '-m', 'kbht_server.cli', 'serve-bootstrap', '--help'], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, 'serve-bootstrap CLI missing'
    assert '--inventory-url' in result.stdout
    for extra in [['--port', '0'], ['--port', '65536'], ['--inventory-url', 'ws://example.test:21002/inventory'], ['--inventory-url', 'ws://127.0.0.1:0/inventory']]:
        result = subprocess.run([sys.executable, '-m', 'kbht_server.cli', 'serve-bootstrap', '--environment', 'test', *extra], capture_output=True, text=True, timeout=15)
        assert result.returncode == 2 and 'Traceback' not in result.stderr


def test_argon2_rehash_and_bounded_corrupt_parameters(pg_engine):
    from argon2 import PasswordHasher
    account = AccountService(pg_engine).register('rehash-user', 'test-only-password')
    old = PasswordHasher(time_cost=1, memory_cost=8192, parallelism=1).hash('test-only-password')
    with pg_engine.begin() as connection:
        connection.execute(text('UPDATE accounts SET password_hash=:hash WHERE id=:id'), {'id': account, 'hash': old})
    assert AccountService(pg_engine).authenticate('rehash-user', 'test-only-password') == account
    with pg_engine.connect() as connection:
        saved = connection.execute(text('SELECT password_hash FROM accounts WHERE id=:id'), {'id': account}).scalar_one()
    assert saved != old and not PasswordHasher().check_needs_rehash(saved)
    # Corrupted records must be rejected before calling an unbounded KDF.
    assert hasattr(importlib.import_module('kbht_server.auth'), '_supported_argon2'), 'bounded stored Argon2 policy missing'
    from kbht_server.auth import _supported_argon2
    assert _supported_argon2(saved)
    assert not _supported_argon2(saved.replace('m=65536', 'm=4294967295'))


def test_auth_rate_limit_and_hash_concurrency_are_global_and_fail_fast(pg_engine):
    from kbht_server.adapters.bootstrap import AuthLimiter
    limiter = AuthLimiter(attempts=1)
    with live_http(app(pg_engine, auth_limiter=limiter)) as base:
        assert request(base, '/v1/sessions', 'POST', credentials('absent-one'))[0] == 401
        assert request(base, '/v1/sessions', 'POST', credentials('absent-two'), headers={'X-Forwarded-For': '1.2.3.4'})[0] == 429
    limiter = AuthLimiter(concurrent_hashes=1)
    with live_http(app(pg_engine, auth_limiter=limiter)) as base:
        with limiter.acquire():
            assert request(base, '/v1/accounts', 'POST', credentials())[0] == 429
        assert request(base, '/v1/accounts', 'POST', credentials())[0] == 201


def test_chunked_size_limit_and_malformed_json_have_fixed_errors(pg_engine):
    with live_http(app(pg_engine)) as base:
        connection = http.client.HTTPConnection('127.0.0.1', int(base.rsplit(':', 1)[1]), timeout=5)
        connection.request('POST', '/v1/accounts', body=iter([b' ' * 2048, b' ' * 2049]), headers={'Content-Type': 'application/json'}, encode_chunked=True)
        response = connection.getresponse()
        assert response.status == 413
        assert json.loads(response.read())['error']['code'] == 'PAYLOAD_TOO_LARGE'
        connection.close()
        connection = http.client.HTTPConnection('127.0.0.1', int(base.rsplit(':', 1)[1]), timeout=5)
        connection.request('POST', '/v1/accounts', body=b'{"password":"private-test-value",broken', headers={'Content-Type': 'application/json'})
        response = connection.getresponse()
        assert response.status == 422 and b'private-test-value' not in response.read()
        connection.close()


def test_bootstrap_revalidates_revocation_after_snapshot_wait(box_lab):
    lab = box_lab
    token = SessionService(lab.engine).issue(ACCOUNT_IDS[10001])
    entered, proceed = Event(), Event()
    def wait_snapshot(connection, cursor, statement, parameters, context, executemany):
        if 'FROM inventory_items' in statement:
            entered.set()
            assert proceed.wait(5)
    event.listen(lab.engine, 'before_cursor_execute', wait_snapshot)
    try:
        with live_http(app(lab.engine)) as base, ThreadPoolExecutor(max_workers=1) as workers:
            future = workers.submit(request, base, '/v1/inventory/bootstrap', 'POST', {'playerId': 10001, 'serverId': 1}, token)
            assert entered.wait(5)
            SessionService(lab.engine).revoke(token)
            proceed.set()
            assert future.result()[0] == 401
    finally:
        proceed.set()
        event.remove(lab.engine, 'before_cursor_execute', wait_snapshot)


def test_unhandled_exception_never_echoed_or_logged(pg_engine, caplog):
    def fail_database(connection, cursor, statement, parameters, context, executemany):
        if 'FROM accounts' in statement:
            raise RuntimeError('private-password private-token SELECT secret')
    event.listen(pg_engine, 'before_cursor_execute', fail_database)
    try:
        with live_http(app(pg_engine)) as base:
            status, result = request(base, '/v1/sessions', 'POST', credentials())
        assert status == 500 and result['error']['code'] == 'INTERNAL_ERROR'
        assert 'private-password' not in json.dumps(result) + caplog.text
    finally:
        event.remove(pg_engine, 'before_cursor_execute', fail_database)


def test_bootstrap_release_unavailable_denies_without_mutation(box_lab):
    lab = box_lab
    token = SessionService(lab.engine).issue(ACCOUNT_IDS[10001])
    with lab.engine.begin() as connection:
        connection.execute(text("UPDATE game_servers SET status='MAINTENANCE'"))
        before = connection.execute(text('SELECT count(*) FROM command_receipts')).scalar_one()
    with live_http(app(lab.engine)) as base:
        assert request(base, '/v1/inventory/bootstrap', 'POST', {'playerId': 10001, 'serverId': 1}, token)[0] == 409
    assert lab.item_quantity(10001, 321) == 2
    with lab.engine.connect() as connection:
        assert connection.execute(text('SELECT count(*) FROM command_receipts')).scalar_one() == before


def test_duplicate_json_keys_and_nonfinite_numbers_rejected(pg_engine):
    with live_http(app(pg_engine)) as base:
        for body in [b'{"login":"first-user","login":"second-user","password":"test-only-password"}', b'{"login":"first-user","password":NaN}']:
            connection = http.client.HTTPConnection('127.0.0.1', int(base.rsplit(':', 1)[1]), timeout=5)
            connection.request('POST', '/v1/accounts', body=body, headers={'Content-Type': 'application/json'})
            response = connection.getresponse()
            assert response.status == 422
            response.read()
            connection.close()
    with pg_engine.connect() as connection:
        assert connection.execute(text('SELECT count(*) FROM accounts')).scalar_one() == 0


def test_reopen_retains_token_and_lock_denies_bootstrap_and_inventory(box_lab):
    from kbht_server.adapters.inventory_connection import InventoryConnection
    from kbht_server.contracts import DomainFailure
    from test_pomelo_inventory import _hello
    lab = box_lab
    token = SessionService(lab.engine).issue(ACCOUNT_IDS[10001])
    connection = InventoryConnection(lab.engine)
    connection.negotiate(token, _hello())
    lab.engine.dispose()
    with live_http(app(lab.engine)) as base:
        assert request(base, '/v1/inventory/bootstrap', 'POST', {'playerId': 10001, 'serverId': 1}, token)[0] == 200
        with lab.engine.begin() as db:
            db.execute(text("UPDATE accounts SET status='LOCKED' WHERE id=:id"), {'id': ACCOUNT_IDS[10001]})
        assert request(base, '/v1/inventory/bootstrap', 'POST', {'playerId': 10001, 'serverId': 1}, token)[0] == 401
        with pytest.raises(DomainFailure) as error:
            connection.resync()
        assert error.value.code == 'UNAUTHENTICATED'
    assert lab.item_quantity(10001, 321) == 2


def test_concurrent_password_change_not_overwritten_during_upgrade(pg_engine):
    from argon2 import PasswordHasher
    account = AccountService(pg_engine).register('race-user', 'test-only-password')
    old = PasswordHasher(time_cost=1, memory_cost=8192, parallelism=1).hash('test-only-password')
    replacement = PasswordHasher().hash('different-test-password')
    with pg_engine.begin() as connection:
        connection.execute(text('UPDATE accounts SET password_hash=:hash WHERE id=:id'), {'id': account, 'hash': old})
    entered, proceed = Event(), Event()
    def wait_upgrade(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith('SELECT password_hash,status'):
            entered.set()
            assert proceed.wait(5)
    event.listen(pg_engine, 'before_cursor_execute', wait_upgrade)
    try:
        with ThreadPoolExecutor(max_workers=1) as workers:
            future = workers.submit(AccountService(pg_engine).authenticate, 'race-user', 'test-only-password')
            assert entered.wait(5)
            with pg_engine.begin() as connection:
                connection.execute(text('UPDATE accounts SET password_hash=:hash WHERE id=:id'), {'id': account, 'hash': replacement})
            proceed.set()
            assert future.result() is None
    finally:
        proceed.set()
        event.remove(pg_engine, 'before_cursor_execute', wait_upgrade)
    with pg_engine.connect() as connection:
        assert connection.execute(text('SELECT password_hash FROM accounts WHERE id=:id'), {'id': account}).scalar_one() == replacement


def test_partial_rejected_body_has_total_read_deadline(pg_engine, monkeypatch):
    import socket
    from kbht_server.adapters import bootstrap
    monkeypatch.setattr(bootstrap, 'BODY_READ_SECONDS', 0.05, raising=False)
    with live_http(app(pg_engine)) as base:
        with socket.create_connection(('127.0.0.1', int(base.rsplit(':', 1)[1])), timeout=1) as connection:
            connection.sendall(b'POST /v1/accounts?denied=1 HTTP/1.1\r\nHost: localhost\r\nContent-Type: application/json\r\nContent-Length: 50\r\n\r\n{')
            assert b'408' in connection.recv(1024).split(b'\r\n')[0]

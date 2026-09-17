import pytest
from uuid import uuid4
from sqlalchemy import text,update

from kbht_server.adapters import native_inventory
from kbht_server.auth import SessionService
from kbht_server.contracts import DomainFailure
from kbht_server.db.schema import game_servers
from pg_lab import ACCOUNT_IDS,CONTENT_ID
from test_fixed_boxes import draft_boxes,box_lab
from test_native_inventory import envelope

CAP='native-inventory-v1'


def connection(lab):
    assert hasattr(native_inventory,'InventoryConnection'),'negotiated connection missing'
    return native_inventory.InventoryConnection(lab.engine)


def hello(player=10001,capabilities=None):
    return {'protocolVersion':1,'capabilities':[CAP] if capabilities is None else capabilities,
            'playerId':player,'serverId':1,'contentVersionId':str(CONTENT_ID)}


def ready(lab):
    token=SessionService(lab.engine).issue(ACCOUNT_IDS[10001])
    conn=connection(lab)
    response=conn.negotiate(token,hello())
    return conn,token,response


def test_negotiate_pins_scope_and_returns_replace_snapshot(box_lab):
    conn,token,response=ready(box_lab)
    assert response['protocolVersion']==1 and response['capability']==CAP
    assert response['snapshotMode']=='replace-bag'
    assert response['snapshot']['version']==box_lab._version(10001)
    assert response['playerId']==10001 and response['serverId']==1
    assert response['allowedRoutes']==['logic.playerHandler.useItem']
    assert response['fullPlayerSnapshot'] is False
    assert token not in repr(conn) and token not in str(response)


def test_unnegotiated_or_closed_connection_cannot_mutate(box_lab):
    conn=connection(box_lab)
    with pytest.raises(DomainFailure) as fail: conn.execute(envelope(box_lab))
    assert fail.value.code=='UNAUTHENTICATED'
    conn,_,_=ready(box_lab)
    conn.close()
    with pytest.raises(DomainFailure) as fail: conn.resync()
    assert fail.value.code=='UNAUTHENTICATED'


@pytest.mark.parametrize('change',[
    {'protocolVersion':True},{'protocolVersion':2},{'capabilities':[]},
    {'capabilities':CAP},{'capabilities':[CAP,CAP]},{'playerId':True},
    {'serverId':0},{'contentVersionId':'bad'},{'accountId':str(ACCOUNT_IDS[10001])},
])
def test_invalid_hello_cannot_create_session_binding(box_lab,change):
    conn=connection(box_lab)
    token=SessionService(box_lab.engine).issue(ACCOUNT_IDS[10001])
    with pytest.raises(DomainFailure): conn.negotiate(token,{**hello(),**change})
    with pytest.raises(DomainFailure): conn.execute(envelope(box_lab))
    assert box_lab.item_quantity(10001,321)==2


def test_failed_renegotiation_clears_previous_identity(box_lab):
    conn,_,_=ready(box_lab)
    with pytest.raises(DomainFailure): conn.negotiate('invalid',hello())
    with pytest.raises(DomainFailure) as fail: conn.execute(envelope(box_lab))
    assert fail.value.code=='UNAUTHENTICATED'


def test_foreign_player_cannot_be_selected(box_lab):
    token=SessionService(box_lab.engine).issue(ACCOUNT_IDS[10001])
    with pytest.raises(DomainFailure) as fail: connection(box_lab).negotiate(token,hello(player=10002))
    assert fail.value.code=='FORBIDDEN'


@pytest.mark.parametrize('field,value',[('player_id',10002),('server_id',2),('content_version_id',str(uuid4()))])
def test_command_cannot_switch_negotiated_scope(box_lab,field,value):
    conn,_,_=ready(box_lab)
    with pytest.raises(DomainFailure) as fail: conn.execute({**envelope(box_lab),field:value})
    assert fail.value.code in ('FORBIDDEN','CONTENT_UNAVAILABLE')
    assert box_lab.item_quantity(10001,321)==2


@pytest.mark.parametrize('action',['revoke','expire','rotate'])
def test_token_state_rechecked_for_each_command_and_snapshot(box_lab,action):
    conn,token,_=ready(box_lab)
    service=SessionService(box_lab.engine)
    if action=='revoke': service.revoke(token)
    elif action=='rotate': service.issue(ACCOUNT_IDS[10001])
    else:
        with box_lab.engine.begin() as c: c.execute(text("UPDATE sessions SET expires_at=now()-interval '1 second'"))
    with pytest.raises(DomainFailure) as fail: conn.execute(envelope(box_lab))
    assert fail.value.code=='UNAUTHENTICATED'
    with pytest.raises(DomainFailure): conn.resync()
    assert box_lab.item_quantity(10001,321)==2


def test_reconnect_retries_original_command_and_replaces_stale_bag(box_lab):
    conn,token,_=ready(box_lab)
    request=envelope(box_lab,count=2)
    saved=conn.execute(request)
    conn.close()
    box_lab.engine.dispose()
    restored=connection(box_lab)
    hello_response=restored.negotiate(token,hello())
    assert request['payload']['bagIndex'] not in hello_response['snapshot']['bag']['items']
    assert restored.execute(request)==saved
    assert box_lab.item_quantity(10001,49902)==12
    assert restored.resync()['snapshot']['version']==saved['version']


def test_stale_command_is_conflict_then_resync_returns_current_state(box_lab):
    conn,_,_=ready(box_lab)
    stale=envelope(box_lab,key='stale')
    box_lab.add_item(10001,321,1,reason='test-other-command')
    with pytest.raises(DomainFailure) as fail: conn.execute(stale)
    assert fail.value.code=='CONFLICT'
    fresh=conn.resync()
    assert fresh['snapshotMode']=='replace-bag'
    assert fresh['snapshot']['version']==box_lab._version(10001)
    assert box_lab.item_quantity(10001,49902)==0


def test_maintenance_blocks_snapshot_not_fake_bootstrap(box_lab):
    conn,_,_=ready(box_lab)
    with box_lab.engine.begin() as c: c.execute(update(game_servers).values(status='MAINTENANCE'))
    with pytest.raises(DomainFailure) as fail: conn.resync()
    assert fail.value.code=='CONTENT_UNAVAILABLE'


def test_connections_cannot_leak_selected_players(box_lab):
    a,_,_=ready(box_lab)
    token_b=SessionService(box_lab.engine).issue(ACCOUNT_IDS[10002])
    b=connection(box_lab)
    b.negotiate(token_b,hello(player=10002))
    with pytest.raises(DomainFailure) as fail: b.execute(envelope(box_lab))
    assert fail.value.code=='FORBIDDEN'
    a.execute(envelope(box_lab))
    assert box_lab.item_quantity(10001,49902)==6
    assert box_lab.item_quantity(10002,49902)==0


def test_hello_unknown_capability_is_not_granted(box_lab):
    token=SessionService(box_lab.engine).issue(ACCOUNT_IDS[10001])
    result=connection(box_lab).negotiate(token,hello(capabilities=['unimplemented',CAP]))
    assert result['capability']==CAP
    assert result['allowedRoutes']==['logic.playerHandler.useItem']


def test_renegotiation_failure_for_foreign_player_clears_binding(box_lab):
    conn,token,_=ready(box_lab)
    with pytest.raises(DomainFailure): conn.negotiate(token,hello(player=10002))
    with pytest.raises(DomainFailure) as fail: conn.execute(envelope(box_lab))
    assert fail.value.code=='UNAUTHENTICATED'


def test_token_is_rechecked_after_snapshot_wait(box_lab):
    from sqlalchemy import event
    token=SessionService(box_lab.engine).issue(ACCOUNT_IDS[10001])
    conn=connection(box_lab)
    fired=False
    def revoke_after_read(connection_,cursor,statement,parameters,context,executemany):
        nonlocal fired
        if 'FROM inventory_items' in statement and not fired:
            fired=True
            SessionService(box_lab.engine).revoke(token)
    event.listen(box_lab.engine,'after_cursor_execute',revoke_after_read)
    try:
        with pytest.raises(DomainFailure) as fail: conn.negotiate(token,hello())
        assert fail.value.code=='UNAUTHENTICATED'
        assert fired
    finally:
        event.remove(box_lab.engine,'after_cursor_execute',revoke_after_read)
    with pytest.raises(DomainFailure): conn.execute(envelope(box_lab))


def test_revocation_during_resync_suppresses_snapshot_and_clears_binding(box_lab):
    from sqlalchemy import event
    conn,token,_=ready(box_lab)
    fired=False
    def revoke_after_read(connection_,cursor,statement,parameters,context,executemany):
        nonlocal fired
        if 'FROM inventory_items' in statement and not fired:
            fired=True
            SessionService(box_lab.engine).revoke(token)
    event.listen(box_lab.engine,'after_cursor_execute',revoke_after_read)
    try:
        with pytest.raises(DomainFailure) as fail: conn.resync()
        assert fail.value.code=='UNAUTHENTICATED' and fired
    finally:
        event.remove(box_lab.engine,'after_cursor_execute',revoke_after_read)
    with pytest.raises(DomainFailure): conn.execute(envelope(box_lab))


def test_close_serializes_after_admitted_command(box_lab):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    from sqlalchemy import event
    conn,_,_=ready(box_lab)
    entered,release,closing,closed=Event(),Event(),Event(),Event()
    def pause(connection_,cursor,statement,parameters,context,executemany):
        if statement.startswith('INSERT INTO command_receipts'):
            entered.set()
            assert release.wait(10)
    def close():
        closing.set()
        conn.close()
        closed.set()
    event.listen(box_lab.engine,'before_cursor_execute',pause)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            writer=pool.submit(conn.execute,envelope(box_lab))
            assert entered.wait(10)
            closer=pool.submit(close)
            assert closing.wait(10)
            assert not closed.wait(0.1)
            release.set()
            assert writer.result(timeout=15)['result']['_temp']['entityCountMap']['49902']==6
            closer.result(timeout=15)
        assert closed.is_set()
    finally:
        release.set()
        event.remove(box_lab.engine,'before_cursor_execute',pause)
    with pytest.raises(DomainFailure) as fail: conn.execute(envelope(box_lab,key='after-close'))
    assert fail.value.code=='UNAUTHENTICATED'
    assert box_lab.item_quantity(10001,49902)==6

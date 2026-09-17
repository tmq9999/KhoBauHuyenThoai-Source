from dataclasses import asdict
import json
from uuid import uuid4

import pytest
from sqlalchemy import text,update

from kbht_server.adapters import commands
from kbht_server.contracts import DomainFailure
from kbht_server.db.schema import game_servers,inventory_items
from pg_lab import ACCOUNT_IDS,CONTENT_ID
from test_fixed_boxes import draft_boxes,box_lab

CAPABILITY='native-inventory-v1'
ROUTE='logic.playerHandler.useItem'


def adapter(lab):
    assert hasattr(commands,'NativeInventoryAdapter'),'native inventory adapter missing'
    return commands.NativeInventoryAdapter(lab.engine)


def snapshot(lab,account=None,player=10001):
    return adapter(lab).snapshot(account or ACCOUNT_IDS[10001],player,1,CONTENT_ID,capability=CAPABILITY)


def envelope(lab,count=1,key='native-use',bag=None):
    if bag is None: bag=str(next(row['id'] for row in lab.items(10001) if row['kind_id']==321))
    cmd=lab.inventory_command(10001,{'bagIndex':bag,'itemCount':count},key=key,route=ROUTE)
    result=json.loads(json.dumps(asdict(cmd),default=str))
    result.pop('account_id')
    return result


def call(lab,body,account=None,capability=CAPABILITY):
    return adapter(lab).execute(account or ACCOUNT_IDS[10001],body,capability=capability)


def test_snapshot_ids_stable_and_source_shape_literal(box_lab):
    inv=next(row['id'] for row in box_lab.items(10001) if row['kind_id']==321)
    first=snapshot(box_lab)
    assert first['bag']=={'items':{str(inv):{'kindId':321,'count':2}}}
    assert first['contentVersionId']==str(CONTENT_ID)
    assert first['version']==box_lab._version(10001)
    box_lab.engine.dispose()
    assert snapshot(box_lab)==first


def test_use_returns_native_delta_and_saved_reward_not_current_snapshot(box_lab):
    request=envelope(box_lab,count=2)
    index=request['payload']['bagIndex']
    first=call(box_lab,request)
    native=first['result']
    assert native['_temp']['route']==ROUTE
    assert native['bag']['items'][index] is None
    assert native['_temp']['entityCountMap']=={
        '40102':2,'40202':2,'40302':2,'40402':2,'40502':2,'40602':2,
        '42102':2,'42202':2,'42302':2,'42402':2,'42502':2,'42602':2,'49902':12}
    assert all(value is None or set(value)=={'kindId','count'} for value in native['bag']['items'].values())
    assert index not in snapshot(box_lab)['bag']['items']
    # Advance state after the receipt; replay must not serialize latest inventory.
    box_lab.add_item(10001,321,1,reason='test-later-box')
    assert call(box_lab,request)==first
    assert box_lab.item_quantity(10001,49902)==12
    with box_lab.engine.connect() as connection:
        stored=connection.execute(text('SELECT result_json FROM command_receipts WHERE command_id=:id'),{'id':first['commandId']}).scalar_one()
        assert stored['result']==native


@pytest.mark.parametrize('bag',[True,10001,'01','0','-1','1.0','1e4',' 10001','9007199254740992','__proto__'])
def test_noncanonical_bag_index_denied_without_consumption(box_lab,bag):
    with pytest.raises(DomainFailure) as failure: call(box_lab,envelope(box_lab,bag=bag))
    assert failure.value.code=='VALIDATION_ERROR'
    assert box_lab.item_quantity(10001,321)==2


def test_foreign_bag_and_account_cannot_mutate_or_snapshot(box_lab):
    foreign=str(next(row['id'] for row in box_lab.items(10002) if row['kind_id']==321))
    with pytest.raises(DomainFailure) as failure: call(box_lab,envelope(box_lab,bag=foreign))
    assert failure.value.code=='NOT_FOUND'
    with pytest.raises(DomainFailure) as failure: call(box_lab,envelope(box_lab),account=ACCOUNT_IDS[10002])
    assert failure.value.code=='FORBIDDEN'
    with pytest.raises(DomainFailure) as failure: snapshot(box_lab,account=ACCOUNT_IDS[10002])
    assert failure.value.code=='FORBIDDEN'


@pytest.mark.parametrize('capability',[None,'legacy','native-inventory-v2'])
def test_no_capability_does_not_silently_accept_legacy_mutation(box_lab,capability):
    with pytest.raises(DomainFailure) as failure: call(box_lab,envelope(box_lab),capability=capability)
    assert failure.value.code=='NOT_IMPLEMENTED'
    assert box_lab.item_quantity(10001,321)==2


def test_unknown_route_extra_payload_and_malformed_envelope_rejected(box_lab):
    request=envelope(box_lab)
    with pytest.raises(DomainFailure): call(box_lab,{**request,'route':'logic.gmHandler.addItem'})
    with pytest.raises(DomainFailure): call(box_lab,{**request,'payload':{**request['payload'],'kindId':321}})
    with pytest.raises(DomainFailure): call(box_lab,{'payload':request['payload']})
    assert box_lab.item_quantity(10001,321)==2


def test_snapshot_requires_active_content_and_exact_scope(box_lab):
    with pytest.raises(DomainFailure) as failure:
        adapter(box_lab).snapshot(ACCOUNT_IDS[10001],10001,1,uuid4(),capability=CAPABILITY)
    assert failure.value.code=='CONTENT_UNAVAILABLE'
    with box_lab.engine.begin() as connection: connection.execute(update(game_servers).values(status='MAINTENANCE'))
    with pytest.raises(DomainFailure) as failure: snapshot(box_lab)
    assert failure.value.code=='CONTENT_UNAVAILABLE'


def test_snapshot_does_not_flatten_unsupported_item_types(box_lab):
    box_lab.add_item(10001,311,1,reason='test-unsupported-native')
    with pytest.raises(DomainFailure) as failure: snapshot(box_lab)
    assert failure.value.code=='NOT_IMPLEMENTED'


def test_native_http_session_roundtrip_and_revocation(box_lab):
    from kbht_server.auth import SessionService
    from kbht_server.adapters.http import create_app
    from test_http_adapter import live_http,post
    native=adapter(box_lab)
    # Connection-scoped negotiated capability, never inferred from request body.
    class Negotiated:
        def execute(self,account_id,body):
            return native.execute(account_id,body,capability=CAPABILITY)
    sessions=SessionService(box_lab.engine)
    token=sessions.issue(ACCOUNT_IDS[10001])
    request=envelope(box_lab)
    with live_http(create_app(Negotiated(),authenticate=sessions.resolve)) as base:
        headers={'Authorization':'Bearer '+token}
        status,result=post(base,request,headers)
        assert status==200
        assert result['result']['_temp']['entityCountMap']['49902']==6
        assert post(base,request,headers)==(status,result)
        sessions.revoke(token)
        assert post(base,request,headers)[0]==401
    assert box_lab.item_quantity(10001,49902)==6


def test_snapshot_rejects_cross_content_inventory(box_lab):
    # Corrupt fixture provenance behind DB guards is not allowed; instead use a
    # separately published version and valid stack FK to exercise mixed release.
    other=uuid4()
    with box_lab.engine.begin() as connection:
        connection.execute(text("INSERT INTO content_versions(id,source_sha256,rules_sha256,status) VALUES (:id,:sha,:sha,'DRAFT')"),{'id':other,'sha':'1'*64})
        connection.execute(text('INSERT INTO item_definitions(content_version_id,kind_id,stack_limit) VALUES (:id,321,1000)'),{'id':other})
        connection.execute(text("UPDATE content_versions SET status='PUBLISHED' WHERE id=:id"),{'id':other})
        connection.execute(inventory_items.insert().values(player_id=10001,content_version_id=other,kind_id=321,stack_key='mixed-release-fixture',quantity=1,version=1))
    with pytest.raises(DomainFailure) as failure: snapshot(box_lab)
    assert failure.value.code=='CONTENT_UNAVAILABLE'


def test_maximum_safe_bag_key_roundtrips_without_float_conversion(box_lab):
    value=9007199254740991
    # Explicit edge fixture; valid PK/FK, not an owned item to grant in gameplay.
    with box_lab.engine.begin() as connection:
        connection.execute(inventory_items.insert().values(id=value,player_id=10001,content_version_id=CONTENT_ID,kind_id=321,stack_key='max-id-fixture',quantity=1,version=1))
    assert snapshot(box_lab)['bag']['items'][str(value)]=={'kindId':321,'count':1}
    result=call(box_lab,envelope(box_lab,bag=str(value)))
    assert result['result']['bag']['items'][str(value)] is None


def test_snapshot_waits_for_committing_player_command(box_lab):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    from sqlalchemy import event
    entered,release=Event(),Event()
    # Pause after the handler inventory/reward changes but before receipt commit.
    def pause(connection,cursor,statement,parameters,context,executemany):
        if statement.startswith('INSERT INTO command_receipts'):
            entered.set()
            assert release.wait(10),'test writer gate timed out'
    event.listen(box_lab.engine,'before_cursor_execute',pause)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            writer=pool.submit(call,box_lab,envelope(box_lab,count=2))
            assert entered.wait(10)
            reader=pool.submit(snapshot,box_lab)
            release.set()
            committed=writer.result(timeout=15)
            read=reader.result(timeout=15)
        assert read['version']==committed['version']
        assert all(row['kindId']!=321 for row in read['bag']['items'].values())
        assert sum(row['count'] for row in read['bag']['items'].values() if row['kindId']==49902)==12
    finally:
        release.set()
        event.remove(box_lab.engine,'before_cursor_execute',pause)

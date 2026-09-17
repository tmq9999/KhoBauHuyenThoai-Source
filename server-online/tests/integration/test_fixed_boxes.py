"""Actual PostgreSQL use-box commands; opening inventory is test-only setup."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import select,text,update
from sqlalchemy.exc import DBAPIError

from kbht_server.contracts import DomainFailure
from kbht_server.db.schema import content_versions,item_definitions
from kbht_server.db.uow import CommandExecutor
from kbht_server.db.migrations import check_invariants
from kbht_server.content import importer
from pg_lab import PGLab,seed_players,CONTENT_ID,ACCOUNT_IDS

SOURCE=Path(__file__).resolve().parents[3]/'client-recovered/src/project.js'
SHA='9776b6e20978d5d911bc0abb85830820bac5a3bfb8db4e65a617c5d18646a818'
MATERIALS=(40102,40202,40302,40402,40502,40602,42102,42202,42302,42402,42502,42602,49902)
ROUTE='inventory.useFixedBox'


def stage(connection,box=321):
    assert hasattr(importer,'stage_fixed_box'),'fixed-box staging missing'
    return importer.stage_fixed_box(connection,CONTENT_ID,box,SOURCE,SHA)


@pytest.fixture
def draft_boxes(pg_engine):
    seed_players(pg_engine,(10001,10002),publish=False)
    with pg_engine.begin() as connection:
        connection.execute(update(content_versions).values(source_sha256=SHA))
        # Explicit TEST stack policy only, not an interpretation of APK maxNum=-1.
        connection.execute(item_definitions.insert(),[
            {'content_version_id':CONTENT_ID,'kind_id':kind,'stack_limit':1000}
            for kind in (321,311,*MATERIALS)])
    return PGLab(pg_engine)


@pytest.fixture
def box_lab(draft_boxes):
    with draft_boxes.engine.begin() as connection:
        stage(connection)
        connection.execute(update(content_versions).values(status='PUBLISHED'))
    draft_boxes.add_item(10001,321,2,reason='test-opening-box')
    draft_boxes.add_item(10002,321,1,reason='test-opening-box')
    return draft_boxes


def handler():
    from kbht_server.economy import rewards
    assert hasattr(rewards,'use_fixed_box'),'fixed-box command missing'
    return rewards.use_fixed_box


def command(lab,quantity=1,key='open-box',player=10001,inventory_id=None):
    if inventory_id is None:
        inventory_id=next(row['id'] for row in lab.items(player) if row['kind_id']==321)
    return lab.inventory_command(player,{'inventory_id':inventory_id,'quantity':quantity},key=key,route=ROUTE)


def execute(lab,cmd):
    return CommandExecutor(lab.engine,{ROUTE:handler()}).execute(cmd)


def test_staging_exact_source_recipe_is_idempotent_and_does_not_publish(draft_boxes):
    with draft_boxes.engine.begin() as connection:
        first=stage(connection)
        assert stage(connection)==first
        assert connection.execute(text('SELECT reward_kind_id,quantity FROM fixed_box_rewards ORDER BY reward_kind_id')).all()==[(kind,6 if kind==49902 else 1) for kind in MATERIALS]
        assert connection.execute(text('SELECT status FROM content_versions')).scalar_one()=='DRAFT'


def test_owned_box_consumption_and_reward_replay_survive_reconnect(box_lab):
    cmd=command(box_lab,2)
    result=execute(box_lab,cmd)
    assert box_lab.item_quantity(10001,321)==0
    assert box_lab.item_quantity(10001,49902)==12
    assert box_lab.item_quantity(10001,40102)==2
    assert result.result['inventory'][str(cmd.payload['inventory_id'])] is None
    assert result.result['consumed']=={'inventory_id':cmd.payload['inventory_id'],'kind_id':321,'quantity':2}
    assert len(result.result['reward']['items'])==13
    assert box_lab.inventory_deltas(10001,321)==[2,-2]
    box_lab.engine.dispose()
    assert execute(box_lab,cmd)==result
    assert box_lab.reward_count(10001,'fixed-box',cmd.command_id)==1
    assert box_lab.receipt_count(cmd.command_id)==1
    assert len(box_lab.events(cmd.command_id))==2
    assert not any(check_invariants(box_lab.engine).values())


@pytest.mark.parametrize('quantity',[True,0,-1,1.5,'1',101])
def test_invalid_quantity_cannot_consume(box_lab,quantity):
    with pytest.raises(DomainFailure) as error:
        execute(box_lab,command(box_lab,quantity))
    assert error.value.code in ('VALIDATION_ERROR','LIMIT_REACHED')
    assert box_lab.item_quantity(10001,321)==2
    assert box_lab.item_quantity(10001,49902)==0


def test_client_cannot_supply_rewards_or_kind(box_lab):
    cmd=command(box_lab)
    with pytest.raises(DomainFailure,match='payload'):
        execute(box_lab,replace(cmd,payload={**cmd.payload,'rewards':{49902:999}}))
    assert box_lab.item_quantity(10001,321)==2


def test_foreign_inventory_and_account_denied(box_lab):
    foreign=command(box_lab,player=10002).payload['inventory_id']
    with pytest.raises(DomainFailure) as error:
        execute(box_lab,command(box_lab,inventory_id=foreign))
    assert error.value.code=='NOT_FOUND'
    with pytest.raises(DomainFailure) as error:
        execute(box_lab,replace(command(box_lab),account_id=ACCOUNT_IDS[10002]))
    assert error.value.code=='FORBIDDEN'
    assert box_lab.item_quantity(10002,321)==1


def test_insufficient_box_and_changed_replay_do_not_grant(box_lab):
    with pytest.raises(DomainFailure) as error:
        execute(box_lab,command(box_lab,3))
    assert error.value.code=='INSUFFICIENT_FUNDS'
    cmd=command(box_lab)
    execute(box_lab,cmd)
    with pytest.raises(DomainFailure) as error:
        execute(box_lab,replace(cmd,payload={**cmd.payload,'quantity':2}))
    assert error.value.code=='CONFLICT'
    assert box_lab.item_quantity(10001,49902)==6


def test_concurrent_same_command_consumes_once(box_lab):
    cmd=command(box_lab)
    barrier=Barrier(2)
    def run(_):
        barrier.wait(timeout=10)
        return execute(box_lab,cmd)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(run,range(2)))
    assert results[0]==results[1]
    assert box_lab.item_quantity(10001,321)==1
    assert box_lab.item_quantity(10001,49902)==6


def test_grant_failure_rolls_back_box_ledger_receipt_and_event(box_lab):
    with box_lab.engine.begin() as connection:
        connection.execute(text('ALTER TABLE inventory_ledger ADD CHECK (NOT(kind_id=49902 AND delta>0))'))
    cmd=command(box_lab)
    with pytest.raises(DBAPIError): execute(box_lab,cmd)
    assert box_lab.item_quantity(10001,321)==2
    assert box_lab.item_quantity(10001,40102)==0
    assert box_lab.receipt_count(cmd.command_id)==0
    assert box_lab.events(cmd.command_id)==[]
    assert not any(check_invariants(box_lab.engine).values())


def test_random_box_explicitly_unsupported(box_lab):
    box_lab.add_item(10001,311,1,reason='test-random-box')
    inv=next(row['id'] for row in box_lab.items(10001) if row['kind_id']==311)
    with pytest.raises(DomainFailure) as error:
        execute(box_lab,command(box_lab,inventory_id=inv))
    assert error.value.code=='NOT_IMPLEMENTED'
    assert box_lab.item_quantity(10001,311)==1


@pytest.mark.parametrize('sql',[
    'UPDATE fixed_box_rewards SET quantity=999',
    'DELETE FROM fixed_box_rewards',
    'TRUNCATE fixed_box_rewards',
    "UPDATE fixed_box_definitions SET source_payload='{}'::jsonb",
])
def test_published_recipes_immutable(box_lab,sql):
    with pytest.raises(DBAPIError),box_lab.engine.begin() as connection: connection.execute(text(sql))


def test_staging_rejects_wrong_source_version_and_missing_item(draft_boxes):
    with draft_boxes.engine.begin() as connection:
        connection.execute(update(content_versions).values(source_sha256='0'*64))
        with pytest.raises(ValueError,match='source'): stage(connection)
    with draft_boxes.engine.begin() as connection:
        connection.execute(update(content_versions).values(source_sha256=SHA))
        connection.execute(text('DELETE FROM item_definitions WHERE kind_id=49902'))
        with pytest.raises(ValueError,match='definition'): stage(connection)
        assert connection.execute(text('SELECT count(*) FROM fixed_box_definitions')).scalar_one()==0


def test_staging_detects_recipe_drift_and_rejects_random(draft_boxes):
    with draft_boxes.engine.begin() as connection:
        with pytest.raises(ValueError,match='unsupported'): stage(connection,311)
        stage(connection)
        connection.execute(text('UPDATE fixed_box_rewards SET quantity=99 WHERE reward_kind_id=49902'))
        with pytest.raises(ValueError,match='mismatch'): stage(connection)


def test_published_recipe_cannot_be_restaged(box_lab):
    with box_lab.engine.begin() as connection:
        with pytest.raises(ValueError,match='DRAFT'): stage(connection)


def test_content_draft_cannot_be_used(draft_boxes):
    cmd=draft_boxes.inventory_command(10001,{'inventory_id':10001,'quantity':1},key='draft-box',route=ROUTE)
    with pytest.raises(DomainFailure) as failure: execute(draft_boxes,cmd)
    assert failure.value.code=='CONTENT_UNAVAILABLE'


def test_reward_capacity_rejection_preserves_owned_box(draft_boxes):
    from kbht_server.db.repositories import MAX_QUANTITY
    with draft_boxes.engine.begin() as connection:
        connection.execute(update(item_definitions).where(item_definitions.c.kind_id==49902).values(stack_limit=MAX_QUANTITY))
        stage(connection)
        connection.execute(update(content_versions).values(status='PUBLISHED'))
    draft_boxes.add_item(10001,321,1,reason='test-opening-box')
    draft_boxes.add_item(10001,49902,MAX_QUANTITY-5,reason='test-capacity-boundary')
    cmd=command(draft_boxes)
    with pytest.raises(DomainFailure) as failure: execute(draft_boxes,cmd)
    assert failure.value.code=='LIMIT_REACHED'
    assert draft_boxes.item_quantity(10001,321)==1
    assert draft_boxes.item_quantity(10001,40102)==0
    assert draft_boxes.item_quantity(10001,49902)==MAX_QUANTITY-5
    assert draft_boxes.receipt_count(cmd.command_id)==0
    assert draft_boxes.events(cmd.command_id)==[]
    assert not any(check_invariants(draft_boxes.engine).values())


@pytest.mark.parametrize('phase,exit_code',[('before-commit',81),('after-commit',82)])
def test_process_loss_before_or_after_box_commit_retries_safely(box_lab,phase,exit_code):
    import subprocess
    import sys
    from test_durability import checked_test_schema
    cmd=command(box_lab)
    schema=checked_test_schema(box_lab.engine)
    child=Path(__file__).parents[1]/'crash_fixed_box.py'
    result=subprocess.run([sys.executable,'-I',str(child),schema,phase,str(cmd.command_id),
                           str(cmd.payload['inventory_id']),str(cmd.expected_version)],
                          capture_output=True,text=True,timeout=30)
    assert result.returncode==exit_code,result.stderr
    if phase=='before-commit':
        assert box_lab.item_quantity(10001,321)==2
        assert box_lab.item_quantity(10001,49902)==0
        assert box_lab.receipt_count(cmd.command_id)==0
        assert box_lab.events(cmd.command_id)==[]
    else:
        assert box_lab.item_quantity(10001,321)==1
        assert box_lab.item_quantity(10001,49902)==6
        assert box_lab.receipt_count(cmd.command_id)==1
    first=execute(box_lab,cmd)
    box_lab.engine.dispose()
    assert execute(box_lab,cmd)==first
    assert box_lab.item_quantity(10001,321)==1
    assert box_lab.item_quantity(10001,49902)==6
    assert box_lab.reward_count(10001,'fixed-box',cmd.command_id)==1
    assert len(box_lab.events(cmd.command_id))==2
    assert not any(check_invariants(box_lab.engine).values())


def test_different_concurrent_commands_cannot_spend_stale_box_version(box_lab):
    first=command(box_lab,2,key='one')
    second=command(box_lab,2,key='two')
    barrier=Barrier(2)
    def run(cmd):
        barrier.wait(timeout=10)
        try: return execute(box_lab,cmd)
        except DomainFailure as failure: return failure.code
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(run,[first,second]))
    assert sum(result=='CONFLICT' for result in results)==1
    assert box_lab.item_quantity(10001,321)==0
    assert box_lab.item_quantity(10001,49902)==12
    assert not any(check_invariants(box_lab.engine).values())


def test_fixed_box_through_authenticated_http_command(box_lab):
    import json
    from dataclasses import asdict
    from kbht_server.adapters.commands import CommandAdapter
    from kbht_server.adapters.http import create_app
    from kbht_server.auth import SessionService
    from test_http_adapter import live_http,post
    sessions=SessionService(box_lab.engine)
    token=sessions.issue(ACCOUNT_IDS[10001])
    adapter=CommandAdapter(CommandExecutor(box_lab.engine,{ROUTE:handler()}),{ROUTE})
    cmd=command(box_lab)
    envelope=json.loads(json.dumps(asdict(cmd),default=str))
    envelope.pop('account_id')
    with live_http(create_app(adapter,authenticate=sessions.resolve)) as base:
        assert post(base,envelope)[0]==401
        status,result=post(base,envelope,{'Authorization':'Bearer '+token})
        assert status==200
        assert result['result']['reward']['items'][-1]=={'kind_id':49902,'quantity':6}
        assert post(base,envelope,{'Authorization':'Bearer '+token})==(status,result)
    assert box_lab.item_quantity(10001,321)==1


def test_runtime_role_can_use_but_not_edit_fixed_box(box_lab):
    from sqlalchemy import event
    from kbht_server.db.session import open_engine
    from kbht_server.db.permissions import grant_runtime_access,UPDATE_COLUMNS
    role='kbht_test_runtime_'+uuid4().hex
    with box_lab.engine.begin() as connection:
        schema=connection.execute(text('SELECT current_schema()')).scalar_one()
        connection.execute(text(f'CREATE ROLE "{role}" NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS'))
        grant_runtime_access(connection,role)
    runtime=open_engine(box_lab.engine.url,schema=schema)
    @event.listens_for(runtime,'connect')
    def assume(dbapi_connection,_):
        dbapi_connection.autocommit=True
        with dbapi_connection.cursor() as cursor: cursor.execute(f'SET ROLE "{role}"')
        dbapi_connection.autocommit=False
    try:
        cmd=command(box_lab)
        result=CommandExecutor(runtime,{ROUTE:handler()}).execute(cmd)
        assert result.result['remaining']==1
        with pytest.raises(DBAPIError) as failure,runtime.begin() as connection:
            connection.execute(text('UPDATE fixed_box_rewards SET quantity=999'))
        assert failure.value.orig.sqlstate=='42501'
    finally:
        runtime.dispose()
        with box_lab.engine.begin() as connection:
            connection.execute(text(f'REVOKE ALL ON ALL TABLES IN SCHEMA "{schema}" FROM "{role}"'))
            for table,columns in UPDATE_COLUMNS.items():
                connection.execute(text(f'REVOKE UPDATE ({",".join(sorted(columns))}) ON "{table}" FROM "{role}"'))
            connection.execute(text(f'REVOKE ALL ON ALL SEQUENCES IN SCHEMA "{schema}" FROM "{role}"'))
            connection.execute(text(f'REVOKE ALL ON SCHEMA "{schema}" FROM "{role}"'))
            connection.execute(text(f'DROP ROLE "{role}"'))

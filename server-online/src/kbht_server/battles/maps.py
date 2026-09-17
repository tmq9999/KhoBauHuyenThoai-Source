"""Server-owned native SMAP starts, resumable exact begin and fixed expiry."""
import json
import re
import secrets
from uuid import UUID, uuid4, uuid5, NAMESPACE_URL
from sqlalchemy import text
from kbht_server.contracts import GameCommand, DomainFailure
from kbht_server.content.native_battles import battle_content, digest
from kbht_server.content.native_players import canonical
from kbht_server.db.uow import UnitOfWork
from kbht_server.players.creation import _receipt, recover_resources
from kbht_server.players.snapshots import locked_player, release_content, validate_session, project_snapshot, fail

BEGIN_ROUTE = 'logic.smapHandler.beginSmap'
END_ROUTE = 'logic.smapHandler.endSmap'


def _integer(v, low, high):
    return type(v) is int and low <= v <= high


def _team(value):
    return (type(value) is list and 1 <= len(value) <= 5 and
            all(type(v) is str and re.fullmatch('[1-5]',v) for v in value) and len(set(value))==len(value))


def validate_begin(body):
    if (type(body) is not dict or set(body)!={'protocolVersion','smapId','teamIndexs'} or
        not _integer(body['protocolVersion'],1,1) or not _integer(body['smapId'],1,1000000000) or not _team(body['teamIndexs'])):
        fail('VALIDATION_ERROR')
    return json.loads(canonical(body))


def validate_end(body):
    if (type(body) is not dict or set(body)!={'protocolVersion','battleId','star','teamIndexs','actions'} or
        not _integer(body['protocolVersion'],1,1) or not _integer(body['star'],0,3) or not _team(body['teamIndexs']) or
        type(body['battleId']) is not str or type(body['actions']) is not list or len(body['actions'])>256):
        fail('VALIDATION_ERROR')
    try:
        if str(UUID(body['battleId'])) != body['battleId']: fail('VALIDATION_ERROR')
    except ValueError: fail('VALIDATION_ERROR')
    previous, seen = (0,0), set()
    for a in body['actions']:
        if (type(a) is not dict or set(a)!={'zone','tick','skillId'} or
            not _integer(a['zone'],1,10) or not _integer(a['tick'],1,1802) or not _integer(a['skillId'],1,1000000000)):
            fail('VALIDATION_ERROR')
        key = (a['zone'],a['tick'],a['skillId'])
        if key in seen or key[:2] < previous: fail('VALIDATION_ERROR')
        seen.add(key); previous = key[:2]
    return json.loads(canonical(body))


def scope(connection, account_id, server_id, player_id, content_id, token):
    player = locked_player(connection,account_id,server_id,player_id)
    release = release_content(connection,server_id,content_id)
    validate_session(connection,account_id,token)
    try: content = battle_content(connection,release)
    except ValueError: fail()
    return player, release, content


def snapshot(connection, player, release):
    login = connection.execute(text('SELECT normalized_login FROM accounts WHERE id=:id'),{'id':player['account_id']}).scalar_one()
    return project_snapshot(connection,player,release,login)


def begin_smap(engine, account_id, server_id, player_id, content_id, token, body, battle_engine):
    body = validate_begin(body)
    if battle_engine is None: fail()
    with engine.begin() as c:
        player,release,content = scope(c,account_id,server_id,player_id,content_id,token)
        existing = c.execute(text("SELECT *,expires_at<=clock_timestamp() AS expired FROM native_battle_sessions WHERE player_id=:id AND status='ACTIVE' FOR UPDATE"),{'id':player_id}).mappings().one_or_none()
        if existing and not existing['expired']:
            if existing['content_version_id']!=content_id or existing['begin_body']!=body: fail('CONFLICT')
            # The session can be revoked/expire while this begin waits on the
            # active-battle row, so a durable replay needs a fresh auth check.
            validate_session(c,account_id,token)
            return existing['begin_response']
        if existing:
            c.execute(text("UPDATE native_battle_sessions SET status='EXPIRED' WHERE id=:id"),{'id':existing['id']})
        stage = content['graph'].get(str(body['smapId']))
        if stage is None or body['smapId'] not in content['bundle']['map_ids']: fail()
        view = snapshot(c,player,release)
        if view['level'] < max(stage['level_limit'],stage['chapter_level_limit']): fail('FORBIDDEN')
        predecessor = stage['predecessor_id']
        if predecessor and not c.execute(text('SELECT EXISTS(SELECT 1 FROM native_map_progress WHERE player_id=:id AND map_id=:map AND star>0)'),{'id':player_id,'map':predecessor}).scalar_one(): fail('FORBIDDEN')
        if not stage['repeatable'] and c.execute(text('SELECT EXISTS(SELECT 1 FROM native_map_progress WHERE player_id=:id AND map_id=:map AND star>0)'),{'id':player_id,'map':body['smapId']}).scalar_one():
            fail('LIMIT_REACHED')
        day = c.execute(text("SELECT ((clock_timestamp() AT TIME ZONE 'Asia/Ho_Chi_Minh')-interval '5 hours')::date")).scalar_one()
        attempts = c.execute(text('SELECT attempts FROM native_battle_attempts WHERE player_id=:id AND smap_id=:map AND reset_day=:day'),{'id':player_id,'map':body['smapId'],'day':day}).scalar_one_or_none() or 0
        if attempts >= stage['times']: fail('LIMIT_REACHED')
        roles = []
        for index in body['teamIndexs']:
            role = view['team']['roles'].get(index)
            if role is None: fail('FORBIDDEN')
            roles.append({'idx':int(index),'kindId':role['kindId'],'level':role['level'],'star':role['star'],
                'awakeLevel':role['awakeLevel'],**role['attr'],'maxHp':role['attr']['hp'],'mp':0,
                'skills':list(role['skills'].values()),'awakeSkills':list(role['awakeSkills'].values())})
        battle_id,seed = uuid4(),secrets.randbelow(0xffffffff)+1
        payload = {'format':'kbht-battle-input-v1','smapId':body['smapId'],'seed':seed,
            'team':{'playerId':player_id,'roles':roles,'ships':[]},'tables':content['bundle']['tables'],'actions':[]}
        # Validate availability/hash before charging; never run a potentially long
        # simulation under the aggregate lock. Actual engine runs at settlement.
        from .engine import ARTIFACT_SHA256
        import hashlib
        try:
            if hashlib.sha256(battle_engine.artifact.read_bytes()).hexdigest()!=ARTIFACT_SHA256 or not battle_engine.node: fail()
        except OSError: fail()
        player = recover_resources(c,player,release)
        command = GameCommand(uuid5(NAMESPACE_URL,'kbht:battle:begin:'+str(battle_id)),account_id,player_id,server_id,
            BEGIN_ROUTE,player['version'],content_id,body)
        work = UnitOfWork(c,command)
        ap = work.adjust_wallet('actionPoint',-stage['action_point'],reason='native-battle-start')
        # Source49510ff only starts a recovery interval after a spend if none
        # is already running; an existing positive deadline keeps its cadence.
        c.execute(text("UPDATE native_player_profiles SET next_action_recover_ms=CASE WHEN :ap >= 60+level THEN 0 WHEN next_action_recover_ms=0 THEN (extract(epoch FROM clock_timestamp())*1000)::bigint+300000 ELSE next_action_recover_ms END WHERE player_id=:id"),{'ap':ap,'id':player_id})
        next_action_recover_ms = c.execute(text('SELECT next_action_recover_ms FROM native_player_profiles WHERE player_id=:id'),{'id':player_id}).scalar_one()
        version = player['version']+1
        result = {'actionPoint':ap,'nextRecoverTimeMap':{'actionPoint':next_action_recover_ms},'version':version,'_temp':{'route':BEGIN_ROUTE,
            'battle':{'protocolVersion':1,'battleId':str(battle_id),'seed':seed,'smapId':body['smapId']},'showEntityIdsMap':{}}}
        c.execute(text("INSERT INTO native_battle_sessions(id,player_id,content_version_id,smap_id,seed,begin_body,battle_input,snapshot_sha256,content_sha256,engine_sha256,begin_response,status) VALUES (:id,:pid,:content,:map,:seed,CAST(:body AS jsonb),CAST(:input AS jsonb),:snapshot,:hash,:engine,CAST(:response AS jsonb),'ACTIVE')"),
            {'id':battle_id,'pid':player_id,'content':content_id,'map':body['smapId'],'seed':seed,'body':canonical(body),'input':canonical(payload),
             'snapshot':digest(payload),'hash':digest(content),'engine':content['engine_sha256'],'response':canonical(result)})
        c.execute(text('INSERT INTO native_battle_attempts(player_id,smap_id,reset_day,attempts) VALUES (:id,:map,:day,1) ON CONFLICT(player_id,smap_id,reset_day) DO UPDATE SET attempts=native_battle_attempts.attempts+1'),{'id':player_id,'map':body['smapId'],'day':day})
        c.execute(text('UPDATE players SET version=:v,updated_at=now() WHERE id=:id'),{'v':version,'id':player_id})
        work.emit('native.battle.started',{'battle_id':str(battle_id),'smap_id':body['smapId'],'snapshot_sha256':digest(payload)})
        _receipt(c,work,result,version)
        validate_session(c,account_id,token)
        return result

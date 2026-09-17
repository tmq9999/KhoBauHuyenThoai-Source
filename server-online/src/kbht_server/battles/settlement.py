"""Compute outside locks, then compare-and-lock and settle exactly once."""
from uuid import UUID, uuid5, NAMESPACE_URL
from sqlalchemy import text
from kbht_server.contracts import GameCommand
from kbht_server.content.native_battles import digest
from kbht_server.content.native_players import canonical
from kbht_server.db.uow import UnitOfWork
from kbht_server.players.creation import _receipt, recover_resources
from kbht_server.players.progression import advance, role_cap, upgrade_action_point
from kbht_server.players.snapshots import validate_session, fail
from .maps import validate_end, scope, snapshot, END_ROUTE
from .engine import BattleEngineError


def _load(c, player_id, content_id, body, content):
    row = c.execute(text('SELECT *,expires_at<=clock_timestamp() AS expired FROM native_battle_sessions WHERE id=:id AND player_id=:pid FOR UPDATE'),
                    {'id':UUID(body['battleId']),'pid':player_id}).mappings().one_or_none()
    if row is None or row['content_version_id']!=content_id: fail('FORBIDDEN')
    if row['begin_body']['teamIndexs']!=body['teamIndexs']: fail('CONFLICT')
    submitted = c.execute(text('SELECT end_body FROM native_battle_submissions WHERE battle_id=:id'),{'id':row['id']}).scalar_one_or_none()
    if submitted is not None and submitted!=body: fail('CONFLICT')
    report = c.execute(text('SELECT end_body,response FROM native_battle_reports WHERE battle_id=:id'),{'id':row['id']}).mappings().one_or_none()
    if report:
        if report['end_body']!=body: fail('CONFLICT')
        return row,report['response']
    if row['status']!='ACTIVE' or row['expired']: fail('CONFLICT')
    if row['snapshot_sha256']!=digest(row['battle_input']) or row['content_sha256']!=digest(content): fail()
    return row,None


def _response(result):
    if result.get('code')==500: fail('CONFLICT')
    return result


def end_smap(engine, account_id, server_id, player_id, content_id, token, body, battle_engine):
    body = validate_end(body)
    if battle_engine is None: fail()
    with engine.begin() as c:
        player,release,content = scope(c,account_id,server_id,player_id,content_id,token)
        row,replay = _load(c,player_id,content_id,body,content)
        if replay is not None:
            # The report-row lock can wait after scope's first auth check.
            validate_session(c,account_id,token)
            return _response(replay)
        immutable_hash = row['snapshot_sha256']
        payload = dict(row['battle_input']); payload['actions'] = body['actions']
        c.execute(text('INSERT INTO native_battle_submissions(battle_id,player_id,end_body,actions_sha256) VALUES (:id,:pid,CAST(:body AS jsonb),:hash) ON CONFLICT(battle_id) DO NOTHING'),
                  {'id':row['id'],'pid':player_id,'body':canonical(body),'hash':digest(body['actions'])})
        validate_session(c,account_id,token)
    try: report = battle_engine.simulate_trusted(payload)
    except BattleEngineError: fail('VALIDATION_ERROR')
    accepted = report['star']==body['star']
    with engine.begin() as c:
        player,release,content = scope(c,account_id,server_id,player_id,content_id,token)
        row,replay = _load(c,player_id,content_id,body,content)
        if replay is not None:
            validate_session(c,account_id,token)
            return _response(replay)
        if row['snapshot_sha256']!=immutable_hash: fail('CONFLICT')
        battle_id = row['id']
        # An accepted report is a player-state boundary. Recover elapsed AP/SP
        # before applying a win's level-derived AP grant; accepted losses also
        # retain their legitimate elapsed recovery without battle rewards.
        if accepted:
            player = recover_resources(c,player,release)
        command = GameCommand(uuid5(NAMESPACE_URL,'kbht:battle:end:'+str(battle_id)),account_id,player_id,server_id,
                              END_ROUTE,player['version'],content_id,body)
        work = UnitOfWork(c,command)
        stage = content['graph'][str(row['smap_id'])]
        if accepted and report['isWin']:
            if stage['coin']:
                work.rewards.grant(source_type='native-battle',source_id=battle_id,currencies={'coin':stage['coin']})
            profile = c.execute(text('SELECT level,experience FROM native_player_profiles WHERE player_id=:id'),{'id':player_id}).mappings().one()
            level,xp = advance(profile['level'],profile['experience'],stage['action_point'],100,content['experience'],'playerExp')
            c.execute(text('UPDATE native_player_profiles SET level=:level,experience=:xp WHERE player_id=:id'),{'id':player_id,'level':level,'xp':xp})
            level_up_ap = sum(upgrade_action_point(destination_level)
                              for destination_level in range(profile['level']+1,level+1))
            if level_up_ap:
                work.adjust_wallet('actionPoint',level_up_ap,reason='native-player-level-up')
            for index in body['teamIndexs']:
                role = c.execute(text('SELECT level,experience FROM native_owned_roles WHERE player_id=:id AND slot=:slot'),{'id':player_id,'slot':int(index)}).mappings().one()
                role_level,role_xp = advance(role['level'],role['experience'],stage['role_exp'],role_cap(level),content['experience'],'roleExp')
                c.execute(text('UPDATE native_owned_roles SET level=:level,experience=:xp WHERE player_id=:id AND slot=:slot'),{'id':player_id,'slot':int(index),'level':role_level,'xp':role_xp})
        if accepted:
            # A level-up can put a recovered AP balance over its new cap.
            # Reuse the source tick normalizer to clear its stale deadline.
            player = recover_resources(c,player,release)
        if accepted:
            c.execute(text('INSERT INTO native_map_progress(player_id,map_type,chapter_id,map_id,star,attempts) VALUES (:id,1,:chapter,:map,:star,1) ON CONFLICT(player_id,map_id) DO UPDATE SET star=GREATEST(native_map_progress.star,excluded.star),attempts=native_map_progress.attempts+1'),
                      {'id':player_id,'chapter':stage['chapter_id'],'map':row['smap_id'],'star':report['star']})
        updated = c.execute(text('UPDATE players SET version=version+1,updated_at=now() WHERE id=:id RETURNING *'),{'id':player_id}).mappings().one()
        view = snapshot(c,updated,release)
        result = {key:view[key] for key in ('level','experience','nextLevelExp','coin','actionPoint','team','power','smapStarMap','smapTimesMap','timesMaxMap','nextRecoverTimeMap')}
        result.update(version=updated['version'],_temp={'route':END_ROUTE,'battleId':str(battle_id),
            'entityCountMap':{},'star':report['star'],'isWin':report['isWin'],
            'rewardPolicy':content['reward_policy']['rules_id']})
        if not accepted:
            result={'code':500,'msg':'Battle result mismatch','_temp':{'route':END_ROUTE,'battleId':str(battle_id)}}
        c.execute(text('INSERT INTO native_battle_reports(battle_id,player_id,end_body,actions_sha256,input_sha256,report,response,command_id) VALUES (:bid,:pid,CAST(:body AS jsonb),:actions,:input,CAST(:report AS jsonb),CAST(:response AS jsonb),:command)'),
            {'bid':battle_id,'pid':player_id,'body':canonical(body),'actions':digest(body['actions']),'input':report['inputSha256'],
             'report':canonical(report),'response':canonical(result),'command':command.command_id})
        work.emit('native.battle.settled',{'battle_id':str(battle_id),'star':report['star'],'is_win':report['isWin'],'accepted':accepted,'report_sha256':digest(report)})
        _receipt(c,work,result,updated['version'])
        if c.execute(text("SELECT status='ACTIVE' AND expires_at>clock_timestamp() FROM native_battle_sessions WHERE id=:id FOR UPDATE"),{'id':battle_id}).scalar_one() is not True:
            fail('CONFLICT')
        c.execute(text("UPDATE native_battle_sessions SET status='SETTLED' WHERE id=:id"),{'id':battle_id})
        validate_session(c,account_id,token)
    return _response(result)

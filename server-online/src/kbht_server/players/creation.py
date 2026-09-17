"""Atomic native onboarding and one-time free rename under PostgreSQL locks."""
import hashlib
import unicodedata
from uuid import NAMESPACE_URL, uuid5
from datetime import datetime, timezone

from sqlalchemy import text
from kbht_server.auth import AccountService
from kbht_server.contracts import GameCommand, DomainFailure
from kbht_server.db.schema import wallets, command_receipts
from kbht_server.db.uow import UnitOfWork
from kbht_server.content.native_players import canonical
from .snapshots import locked_player, release_content, validate_session, project_snapshot, fail


def _receipt(connection, work, result, version):
    envelope = {'content_version_id':str(work.command.content_version_id),'result':result,
                'event_ids':[str(v) for v in work.event_ids]}
    connection.execute(command_receipts.insert().values(
        player_id=work.command.player_id,command_id=work.command.command_id,route=work.command.route,
        payload_hash=hashlib.sha256(canonical(work.command.payload).encode()).hexdigest(),
        result_json=envelope,aggregate_version=version,status='COMMITTED',content_version_id=work.command.content_version_id))


def recover_resources(connection, player, release):
    """Source49510ff: 300000ms tick; published policy supplies skill cap semantics."""
    profile = connection.execute(text('SELECT * FROM native_player_profiles WHERE player_id=:id'),{'id':player['id']}).mappings().one_or_none()
    if profile is None or profile['content_version_id']!=release['content_version_id']:
        fail()
    now_ms = int(datetime.now(timezone.utc).timestamp()*1000)
    changes, deadlines = {}, {}
    for currency,column,cap in (('actionPoint','next_action_recover_ms',60+profile['level']),('skillPoint','next_skill_recover_ms',profile['skill_point_cap'])):
        balance = connection.execute(text('SELECT balance FROM wallets WHERE player_id=:id AND currency=:currency'),{'id':player['id'],'currency':currency}).scalar_one()
        deadline = profile[column]
        if balance>=cap:
            next_deadline = 0
        elif deadline==0:
            next_deadline = now_ms+300000
        elif deadline<=now_ms:
            amount = min(cap-balance,1+(now_ms-deadline)//300000)
            changes[currency] = amount
            next_deadline = 0 if balance+amount>=cap else deadline+amount*300000
        else:
            next_deadline = deadline
        deadlines[column] = next_deadline
    if not changes and all(profile[k]==v for k,v in deadlines.items()):
        return player
    command = GameCommand(uuid5(NAMESPACE_URL,f"kbht:native:recover:{player['id']}:{player['version']}"),player['account_id'],player['id'],player['server_id'],
        'internal.nativeResourceRecovery',player['version'],release['content_version_id'],{'deltas':changes,'deadlines':deadlines})
    work = UnitOfWork(connection,command)
    for currency,amount in changes.items():
        work.adjust_wallet(currency,amount,reason='native-resource-recovery')
    connection.execute(text('UPDATE native_player_profiles SET next_action_recover_ms=:next_action_recover_ms,next_skill_recover_ms=:next_skill_recover_ms WHERE player_id=:id'),{'id':player['id'],**deadlines})
    work.emit('native.resources.recovered',{'deltas':changes,'deadlines':deadlines})
    updated = connection.execute(text('UPDATE players SET version=version+1,updated_at=now() WHERE id=:id RETURNING *'),{'id':player['id']}).mappings().one()
    _receipt(connection,work,{'deltas':changes,'deadlines':deadlines},updated['version'])
    return updated


def create_player(engine, account_id, server_id, name, content_id, token):
    if not isinstance(name,str) or not 3<=len(name)<=64:
        fail('VALIDATION_ERROR')
    try:
        normalized = AccountService._normalize(name)
    except ValueError:
        fail('VALIDATION_ERROR')
    with engine.begin() as connection:
        # An account lock covers the absent-player case, including concurrent
        # retries on separate connectors. No advisory/global creation lock.
        account = connection.execute(text('SELECT normalized_login,status FROM accounts WHERE id=:id FOR UPDATE'),{'id':account_id}).mappings().one_or_none()
        if account is None or account['status']!='ACTIVE':
            fail('UNAUTHENTICATED')
        if normalized!=account['normalized_login']:
            fail('VALIDATION_ERROR')
        existing = connection.execute(text('SELECT * FROM players WHERE account_id=:account AND server_id=:server FOR UPDATE'),{'account':account_id,'server':server_id}).mappings().one_or_none()
        release = release_content(connection,server_id,content_id)
        validate_session(connection,account_id,token)
        if existing is not None:
            existing = recover_resources(connection,existing,release)
            result = project_snapshot(connection,existing,release,account['normalized_login'])
            validate_session(connection,account_id,token)
            return result
        policy, definitions = release['policy'],release['definitions']
        # Sequence is globally shared and JS-safe. Existing historical identities
        # were included by migration; later out-of-band ID collisions fail closed.
        player_id = connection.execute(text("SELECT nextval('native_player_id_seq')")).scalar_one()
        player = connection.execute(text('INSERT INTO players(id,account_id,server_id,name,version) VALUES (:id,:account,:server,:name,1) RETURNING *'),
            {'id':player_id,'account':account_id,'server':server_id,'name':account['normalized_login']}).mappings().one()
        next_tick = int(datetime.now(timezone.utc).timestamp()*1000)+300000
        connection.execute(text('INSERT INTO native_player_profiles(player_id,content_version_id,rules_id,level,experience,first_rename_completed,photo_img_id,ship_img_id,skill_point_cap,next_action_recover_ms,next_skill_recover_ms,vip_level,vip_top_up_gem,vip_gift_gem,buy_action_point_times,buy_skill_point_times) VALUES (:id,:content,:rules,1,0,false,1001,901,:cap,:ap_tick,:sp_tick,0,0,0,0,0)'),
            {'id':player_id,'content':content_id,'rules':release['rules_id'],'cap':policy['skill_point_cap'],'ap_tick':next_tick,'sp_tick':next_tick if policy['skill_point_cap']>10 else 0})
        connection.execute(text('INSERT INTO native_owned_roles(player_id,slot,content_version_id,kind_id,star,level,experience,awake_level,awake_rate_increase_times) VALUES (:id,1,:content,:kind,:star,1,0,0,0)'),
            {'id':player_id,'content':content_id,'kind':definitions['role']['kindId'],'star':definitions['soul']['star']})
        connection.execute(text('INSERT INTO native_role_equipment(player_id,role_slot,equipment_slot,kind_id,level) VALUES (:id,1,:slot,:kind,1)'),
            [{'id':player_id,'slot':slot,'kind':kind} for slot,kind in enumerate(definitions['role']['initEvlItemIds'],1)])
        for group,key in (('skills','skills'),('awakeSkills','awake_skills')):
            for kind,level in policy[key].items():
                connection.execute(text('INSERT INTO native_role_skills(player_id,role_slot,kind_id,skill_group,level) VALUES (:id,1,:kind,:group,:level)'),
                    {'id':player_id,'kind':int(kind),'group':group,'level':level})
        connection.execute(wallets.insert(),[{'player_id':player_id,'currency':currency,'balance':0,'version':0}
            for currency in ('coin','gem','actionPoint','skillPoint')])
        command = GameCommand(uuid5(NAMESPACE_URL,f'kbht:native:create:{account_id}:{server_id}'),account_id,player_id,server_id,
            'connector.playerHandler.createPlayer',0,content_id,{'name':account['normalized_login'],'rules_id':release['rules_id']})
        work = UnitOfWork(connection,command)
        # All opening currencies use shared balanced issuance/ledger/reward receipt.
        work.rewards.grant(source_type='native-player-opening',source_id=command.command_id,
                           currencies={'gem':50,'actionPoint':60,'skillPoint':10})
        work.emit('native.player.created',{'player_id':player_id,'role_slot':1,'role_kind_id':100101,'rules_id':release['rules_id']})
        _receipt(connection,work,{'player_id':player_id},1)
        result = project_snapshot(connection,player,release,account['normalized_login'])
        # Recheck expiry using clock_timestamp, not the transaction start time.
        validate_session(connection,account_id,token)
        return result


def rename_player(engine, account_id, server_id, player_id, name, content_id, token):
    if (not isinstance(name,str) or not 1<=len(name)<=32 or name!=name.strip() or
        any(unicodedata.category(ch).startswith('C') for ch in name)):
        fail('VALIDATION_ERROR')
    with engine.begin() as connection:
        player = locked_player(connection,account_id,server_id,player_id)
        release = release_content(connection,server_id,content_id)
        validate_session(connection,account_id,token)
        profile = connection.execute(text('SELECT first_rename_completed,content_version_id,rules_id FROM native_player_profiles WHERE player_id=:id FOR UPDATE'),{'id':player_id}).mappings().one_or_none()
        if profile is None or profile['content_version_id']!=content_id or profile['rules_id']!=release['rules_id']:
            fail()
        if name==player['name']:
            validate_session(connection,account_id,token)
            return {'name':name}
        if profile['first_rename_completed']:
            # Native rename has no durable caller command key. Never charge on a
            # retry until the paid command envelope is available.
            raise DomainFailure('NOT_IMPLEMENTED','Paid rename requires durable command')
        command = GameCommand(uuid5(NAMESPACE_URL,f'kbht:native:first-rename:{player_id}'),account_id,player_id,server_id,
            'logic.playerHandler.rename',player['version'],content_id,{'name':name})
        work = UnitOfWork(connection,command)
        connection.execute(text('UPDATE players SET name=:name,version=version+1,updated_at=now() WHERE id=:id'),{'name':name,'id':player_id})
        connection.execute(text('UPDATE native_player_profiles SET first_rename_completed=true WHERE player_id=:id'),{'id':player_id})
        work.emit('native.player.renamed',{'name':name,'free':True})
        result = {'name':name}
        _receipt(connection,work,result,player['version']+1)
        validate_session(connection,account_id,token)
        return result

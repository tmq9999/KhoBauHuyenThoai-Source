"""Immutable battle content. Missing reward interpretation blocks before AP debit.

No default reward policy is provided. The supported no-item rule is an explicit
NEW rule requiring owner approval, not recovered specifyDropValues semantics.
"""
import hashlib
import re
from pathlib import Path
from uuid import UUID, uuid5, NAMESPACE_URL
from sqlalchemy import text
from .native_players import SOURCE_SHA, canonical, read_native_player_content, prepare_native_player_content
from .native_tutorial import read_tutorial_content
from .battle_bundle import battle_bundle, CLIENT_LOOKUP_POLICY
from .source import read_table
from .validation import normal_map_graph
from kbht_server.battles.engine import ARTIFACT_SHA256


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def validate_reward_policy(policy):
    keys = {'rules_id','origin','provenance','drop_rule','player_exp_rule','loss_rule','role_exp_rule','attempt_rule'}
    if type(policy) is not dict or set(policy) != keys:
        raise ValueError('explicit approved battle reward policy required')
    if (policy['origin'] != 'owner-approved-new-rule' or
        policy['drop_rule'] != 'no-item-drops-v1' or
        policy['player_exp_rule'] != 'source-ap-times-one-v1' or
        policy['role_exp_rule'] != 'source-selected-team-on-win-v1' or
        policy['loss_rule'] != 'no-rewards-no-refund-v1' or
        policy['attempt_rule'] != 'source-limit-per-vietnam-5am-day-v1'):
        raise ValueError('unsupported battle reward policy')
    for key,maximum in (('rules_id',160),('provenance',2000)):
        if type(policy[key]) is not str or not policy[key].strip() or len(policy[key])>maximum:
            raise ValueError('battle reward approval provenance required')
    return policy


def read_battle_content(source, reward_policy, map_ids):
    validate_reward_policy(reward_policy)
    source = Path(source)
    tables = {name:read_table(source,SOURCE_SHA,name,allow_missing_trailing=True)
              for name in ('bmapData','smapData','experienceData')}
    graph = normal_map_graph(tables['bmapData'],tables['smapData'])
    # Native map views use truthiness: missing/null/0 is nonrepeatable.
    for stage_id, stage in graph.items():
        repeatable = tables['smapData'][stage_id].get('repeatable')
        if repeatable is not None and (type(repeatable) is not int or repeatable not in (0,1)):
            raise ValueError('unsupported map repeatability')
        stage['repeatable'] = repeatable == 1
    if any(v not in graph for v in map_ids):
        raise ValueError('normal maps only')
    xp = {str(row['level']):row for row in tables['experienceData'].values() if 1 <= row['level'] <= 100}
    if len(xp)!=100:
        raise ValueError('incomplete experience levels')
    bundle = battle_bundle(source,map_ids,[100101,100201,100301],lookup_policy=CLIENT_LOOKUP_POLICY)
    return {'format':'native-battle-content-v1','bundle':bundle,
            'graph':{str(k):v for k,v in graph.items()},'experience':xp,
            'engine_sha256':ARTIFACT_SHA256,'reward_policy':reward_policy,
            'source_refs':['project.js:12815-12817','project.js:49464-49484',
                           'project.js:49602-49606','project.js:49698-49700','project.js:49880-49882'],
            'expiry_policy':'server-authored-15-minutes-v1','power_rule':'owned-role-level-v1'}


def battle_content(connection, release, *, required=True):
    # Old0015 listeners/content stay readable without probing a missing table.
    if connection.execute(text("SELECT to_regclass('native_battle_content')")).scalar_one() is None:
        if required: raise ValueError('battle content unavailable')
        return None
    row = connection.execute(text('SELECT * FROM native_battle_content WHERE content_version_id=:id'),
                             {'id':release['content_version_id']}).mappings().one_or_none()
    if row is None:
        if required: raise ValueError('battle content unavailable')
        return None
    definition = row['definitions']
    if (row['source_sha256']!=SOURCE_SHA or row['rules_id']!=release['rules_id'] or
        digest(definition)!=row['definition_sha256'] or definition['engine_sha256']!=ARTIFACT_SHA256):
        raise ValueError('battle release binding mismatch')
    validate_reward_policy(definition['reward_policy'])
    return definition


def _target(c, disposable):
    database,schema = c.execute(text('SELECT current_database(),current_schema()')).one()
    if not ((disposable and database=='kbht_test' and re.fullmatch('kbht_t_[0-9a-f]{32}',schema or '')) or
            (not disposable and database=='kbht_dev' and schema=='kbht_core')):
        raise ValueError('explicit local battle setup target required')
    if c.execute(text('SELECT version_num FROM alembic_version')).scalar_one()!='0016_native_battles':
        raise ValueError('battle setup requires0016')


def prepare_battle_release(c, server_id, previous, source, reward_policy, map_ids, *, disposable=False):
    """NEW immutable DRAFT only. Explicit policy required before any writes."""
    validate_reward_policy(reward_policy)
    _target(c,disposable)
    previous = UUID(str(previous))
    old = c.execute(text("SELECT n.* FROM native_player_content n JOIN content_versions v ON v.id=n.content_version_id WHERE n.content_version_id=:id AND v.status='PUBLISHED'"),{'id':previous}).mappings().one()
    base = read_native_player_content(Path(source),SOURCE_SHA,old['policy'])
    tutorial = read_tutorial_content(source,SOURCE_SHA,old['policy'])
    old_tutorial = c.execute(text('SELECT definitions FROM native_tutorial_content WHERE content_version_id=:id'),{'id':previous}).scalar_one()
    if base!=old['definitions'] or tutorial!=old_tutorial or old['policy']['power_second_argument']!=1:
        raise ValueError('only exact approved tutorial predecessor supported')
    definitions = read_battle_content(source,reward_policy,map_ids)
    version = uuid5(NAMESPACE_URL,'kbht:native-battle:'+str(previous)+':'+digest(definitions))
    if c.execute(text('SELECT active_content_version_id FROM game_servers WHERE id=:id FOR UPDATE'),{'id':server_id}).scalar_one()!=previous:
        raise ValueError('prior active release mismatch')
    rules_hash = digest({'opening':old['definition_sha256'],'tutorial':digest(tutorial),'battle':digest(definitions)})
    existing = c.execute(text('SELECT * FROM content_versions WHERE id=:id'),{'id':version}).mappings().one_or_none()
    if existing:
        saved = c.execute(text('SELECT definitions FROM native_battle_content WHERE content_version_id=:id'),{'id':version}).scalar_one_or_none()
        if existing['status']!='DRAFT' or existing['rules_sha256']!=rules_hash or saved!=definitions:
            raise ValueError('battle draft drift or published')
        return {'content_version_id':str(version),'status':'DRAFT'}
    c.execute(text("INSERT INTO content_versions(id,source_sha256,rules_sha256,status) VALUES (:id,:source,:rules,'DRAFT')"),{'id':version,'source':SOURCE_SHA,'rules':rules_hash})
    prepare_native_player_content(c,version,source,SOURCE_SHA,old['policy'])
    for table,value in (('native_tutorial_content',tutorial),('native_battle_content',definitions)):
        c.execute(text(f'INSERT INTO {table}(content_version_id,source_sha256,rules_id,definition_sha256,definitions) VALUES (:id,:source,:rules,:hash,CAST(:definition AS jsonb))'),
                  {'id':version,'source':SOURCE_SHA,'rules':old['rules_id'],'hash':digest(value),'definition':canonical(value)})
    return {'content_version_id':str(version),'status':'DRAFT'}


def activate_battle_release(c, server_id, previous, version, source, reward_policy, map_ids, *, stopped_listener=False, disposable=False):
    """Explicit stopped-listener cutover; all history keeps original release IDs."""
    if stopped_listener is not True: raise ValueError('stopped listener acknowledgement required')
    _target(c,disposable)
    previous,version = UUID(str(previous)),UUID(str(version))
    c.execute(text('LOCK TABLE accounts,players,game_servers,content_versions,native_player_profiles,native_owned_roles,native_role_equipment,native_role_skills,native_map_progress,native_tutorial_claims,inventory_items,native_battle_sessions IN SHARE ROW EXCLUSIVE MODE'))
    prepared = prepare_battle_release(c,server_id,previous,source,reward_policy,map_ids,disposable=disposable)
    if prepared['content_version_id']!=str(version): raise ValueError('explicit battle release mismatch')
    old = c.execute(text('SELECT * FROM native_player_content WHERE content_version_id=:id'),{'id':previous}).mappings().one()
    tutorial = read_tutorial_content(source,SOURCE_SHA,old['policy'])
    roles = {100101:old['definitions'],**{int(k):v for k,v in tutorial['roles'].items()}}
    players = c.execute(text('SELECT p.*,n.level,n.experience,n.content_version_id,n.rules_id FROM players p LEFT JOIN native_player_profiles n ON n.player_id=p.id WHERE p.server_id=:server'),{'server':server_id}).mappings().all()
    for player in players:
        pid=player['id']
        if player['content_version_id']!=previous or player['rules_id']!=old['rules_id'] or player['level']!=1 or player['experience']!=0:
            raise ValueError('incompatible profile')
        claims=set(c.execute(text('SELECT draw_kind FROM native_tutorial_claims WHERE player_id=:id'),{'id':pid}).scalars())
        expected=[(1,100101)]+([(2,100201)] if 'coin' in claims else [])+([(3,100301)] if 'gem' in claims else [])
        actual=c.execute(text('SELECT slot,kind_id,content_version_id,star,level,experience,awake_level,awake_rate_increase_times FROM native_owned_roles WHERE player_id=:id ORDER BY slot'),{'id':pid}).all()
        if actual!=[(s,k,previous,1,1,0,0,0) for s,k in expected] or ('gem' in claims and 'coin' not in claims):
            raise ValueError('incompatible tutorial roles')
        eq=c.execute(text('SELECT role_slot,equipment_slot,kind_id,level FROM native_role_equipment WHERE player_id=:id ORDER BY role_slot,equipment_slot'),{'id':pid}).all()
        if eq!=[(s,n,k,1) for s,kind in expected for n,k in enumerate(roles[kind]['role']['initEvlItemIds'],1)]: raise ValueError('incompatible equipment')
        skills=c.execute(text('SELECT role_slot,kind_id,skill_group,level FROM native_role_skills WHERE player_id=:id ORDER BY role_slot,kind_id'),{'id':pid}).all()
        if skills!=[(s,roles[k]['role']['skillIds'][0],'skills',1) for s,k in expected]: raise ValueError('incompatible skills')
        for table in ('native_map_progress','native_battle_sessions','inventory_items'):
            if c.execute(text(f'SELECT EXISTS(SELECT 1 FROM {table} WHERE player_id=:id)'),{'id':pid}).scalar_one(): raise ValueError('existing gameplay needs separate migration')
    # Reject unrelated content definitions/assets rather than silently orphaning.
    allowed={'native_player_content','native_tutorial_content','native_player_profiles','native_owned_roles','native_tutorial_claims','command_receipts','reward_grants'}
    quote=c.dialect.identifier_preparer.quote_identifier
    for table in c.execute(text("SELECT table_name FROM information_schema.columns WHERE table_schema=current_schema() AND column_name='content_version_id'")).scalars():
        if table not in allowed and c.execute(text(f'SELECT EXISTS(SELECT 1 FROM {quote(table)} WHERE content_version_id=:id)'),{'id':previous}).scalar_one():
            raise ValueError('unreviewed old content dependency')
    c.execute(text("UPDATE content_versions SET status='PUBLISHED' WHERE id=:id AND status='DRAFT'"),{'id':version})
    for table in ('native_player_profiles','native_owned_roles'):
        c.execute(text(f'UPDATE {table} SET content_version_id=:new WHERE player_id IN (SELECT id FROM players WHERE server_id=:server) AND content_version_id=:old'),{'new':version,'old':previous,'server':server_id})
    c.execute(text('UPDATE game_servers SET active_content_version_id=:new WHERE id=:server AND active_content_version_id=:old'),{'new':version,'old':previous,'server':server_id})
    return {'content_version_id':str(version),'migrated_players':len(players),'status':'PUBLISHED_NOT_NATIVE_CONFIRMED'}

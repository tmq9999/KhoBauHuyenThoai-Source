"""Pinned first-draw definitions and explicit opening-to-tutorial release cutover.

Never runs source JS, updates a published definition, or publishes on a request.
"""
import hashlib
import re
from pathlib import Path
from uuid import UUID, NAMESPACE_URL, uuid5

from sqlalchemy import text
from .source import read_table
from .native_players import (SOURCE_SHA, canonical, validate_policy,
                             read_native_player_content, prepare_native_player_content,
                             _selected_archive)

TUTORIAL_RULE = 'source-first-coin-gem-once-v1'


def read_tutorial_content(source, source_sha, policy):
    source = Path(source)
    policy = validate_policy(policy)
    base = read_native_player_content(source,source_sha,policy)
    if policy['skills']!={'100101':1}:
        raise ValueError('tutorial requires approved first-source-skill level1 opening rule')
    tables = {name:read_table(source,source_sha,name,allow_missing_trailing=True)
              for name in ('dropData','roleData','entityData','soulData','evolutionItemData')}
    draws, roles = {}, {}
    for kind, class_id, drop_id, role_id, slot, cooldown in (
            ('coin',101,10001,100201,2,300000),('gem',201,10028,100301,3,172800000)):
        selected = [row for row in tables['dropData'].values() if row['classId']==class_id]
        expected = {'kindId':drop_id,'classId':class_id,'groupId':1,'refClassId':0,
                    'entityId':role_id,'weight':1,'count':1,'extra':{'star':1}}
        if selected != [expected]:
            raise ValueError('tutorial drop is not the exact deterministic source row')
        role = tables['roleData'][role_id]
        soul = [r for r in tables['soulData'].values() if r['classId']==role['classId']]
        if (len(soul)!=1 or soul[0]['star']!=1 or len(role['initEvlItemIds'])!=6 or
                tables['entityData'][role_id]['type']!='role'):
            raise ValueError('invalid tutorial role dependencies')
        skills = _selected_archive(source,source_sha,'fightSkillData',set(role['skillIds'])|{role['initSkillId']})
        # Only the owned first skill is active. Later passive skills (including
        # Zoro's multiplicative speed buff) are archived, never projected/owned.
        first_skill = skills[str(role['skillIds'][0])]
        buffs = _selected_archive(source,source_sha,'buffData',
                    set(first_skill['buffIds']) if first_skill['type']==3 else set())
        for buff in buffs.values():
            if (not buff.get('isAttacker') or not isinstance(buff.get('extra'),dict) or
                    set(buff['extra'])-{'maxHp','hp','atk','def','mdef','crit','dodge','growth','symbol'} or
                    buff['extra'].get('symbol')!='+'):
                raise ValueError('unsupported tutorial passive stats')
        roles[str(role_id)] = {'role':role,'entity':tables['entityData'][role_id],
            'soul':soul[0],'skills':skills,'buffs':buffs,
            'equipment':{str(v):tables['evolutionItemData'][v] for v in role['initEvlItemIds']}}
        draws[kind] = {'source_drop_id':drop_id,'slot':slot,'cooldown_ms':cooldown,
                      'drop':{'entityId':role_id,'count':1,'extra':{'star':1}}}
    # No friendship is complete with these three source roles; do not guess an
    # unobserved server mapping from numeric friendship type to attribute name.
    classes = {1,2,3}
    if any(set(row['requiredClassIds'])<=classes for row in base['friendship'].values()):
        raise ValueError('tutorial friendship needs a reviewed attribute rule')
    return {'format':TUTORIAL_RULE,'roles':roles,'draws':draws,
            'owned_skill_rule':'first-source-skill-level1','friendship_rule':'no-complete-group'}


def tutorial_content(connection, release):
    row = connection.execute(text('SELECT * FROM native_tutorial_content WHERE content_version_id=:id'),
                             {'id':release['content_version_id']}).mappings().one_or_none()
    if row is None:
        return None
    definitions = row['definitions']
    if (row['source_sha256']!=SOURCE_SHA or row['rules_id']!=release['rules_id'] or
            hashlib.sha256(canonical(definitions).encode()).hexdigest()!=row['definition_sha256'] or
            definitions.get('format')!=TUTORIAL_RULE):
        raise ValueError('tutorial content binding mismatch')
    return definitions


def _target(connection, disposable):
    database,schema = connection.execute(text('SELECT current_database(),current_schema()')).one()
    allowed = (database=='kbht_test' and re.fullmatch(r'kbht_t_[0-9a-f]{32}',schema or '')) if disposable else (database=='kbht_dev' and schema=='kbht_core')
    if not allowed or connection.execute(text('SELECT version_num FROM alembic_version')).scalars().all()!=['0015_native_tutorial']:
        raise ValueError('tutorial setup requires explicit local target at0015')


def _release_spec(connection, previous, source):
    old = connection.execute(text('SELECT n.*,c.status FROM native_player_content n JOIN content_versions c ON c.id=n.content_version_id WHERE n.content_version_id=:id'),{'id':previous}).mappings().one_or_none()
    if old is None or old['status']!='PUBLISHED' or old['source_sha256']!=SOURCE_SHA:
        raise ValueError('published pinned native opening release required')
    base = read_native_player_content(Path(source),SOURCE_SHA,old['policy'])
    if base!=old['definitions'] or hashlib.sha256(canonical({'definitions':base,'policy':old['policy']}).encode()).hexdigest()!=old['definition_sha256']:
        raise ValueError('prior native opening definition drift')
    definitions = read_tutorial_content(source,SOURCE_SHA,old['policy'])
    digest = hashlib.sha256(canonical(definitions).encode()).hexdigest()
    version = uuid5(NAMESPACE_URL,f'kbht:{TUTORIAL_RULE}:{previous}:{digest}')
    return old,definitions,digest,version


def prepare_tutorial_release(connection, server_id, previous, source, *, disposable=False):
    """Caller owns transaction. Create a NEW draft only; no profile/server writes."""
    _target(connection,disposable)
    old,definitions,digest,version = _release_spec(connection,previous,source)
    server = connection.execute(text('SELECT active_content_version_id FROM game_servers WHERE id=:id FOR UPDATE'),{'id':server_id}).scalar_one_or_none()
    if server!=previous:
        raise ValueError('expected prior server release required')
    rules_hash = hashlib.sha256(canonical({'opening':old['definition_sha256'],'tutorial':digest}).encode()).hexdigest()
    saved = connection.execute(text('SELECT * FROM content_versions WHERE id=:id FOR UPDATE'),{'id':version}).mappings().one_or_none()
    if saved is None:
        connection.execute(text("INSERT INTO content_versions(id,source_sha256,rules_sha256,status) VALUES (:id,:source,:rules,'DRAFT')"),{'id':version,'source':SOURCE_SHA,'rules':rules_hash})
    elif saved['status']!='DRAFT' or saved['source_sha256']!=SOURCE_SHA or saved['rules_sha256']!=rules_hash:
        raise ValueError('tutorial draft drift or already published')
    prepare_native_player_content(connection,version,source,SOURCE_SHA,old['policy'])
    existing = connection.execute(text('SELECT * FROM native_tutorial_content WHERE content_version_id=:id'),{'id':version}).mappings().one_or_none()
    expected = {'content_version_id':version,'source_sha256':SOURCE_SHA,'rules_id':old['rules_id'],
                'definition_sha256':digest,'definitions':definitions}
    if existing is None:
        connection.execute(text('INSERT INTO native_tutorial_content(content_version_id,source_sha256,rules_id,definition_sha256,definitions) VALUES (:content_version_id,:source_sha256,:rules_id,:definition_sha256,CAST(:definitions AS jsonb))'),{**expected,'definitions':canonical(definitions)})
    elif dict(existing)!=expected:
        raise ValueError('tutorial draft definitions drift')
    return {'content_version_id':str(version),'previous_content_version_id':str(previous),
            'definition_sha256':digest,'status':'DRAFT'}


def activate_tutorial_release(connection, server_id, previous, version, source, *, disposable=False):
    """Explicit stopped-listener administrative cutover, never called by runtime.

    Migrates only source-identical opening profiles. Historical command/reward
    rows keep their old release IDs, and core receipt replay remains unchanged.
    """
    _target(connection,disposable)
    previous,version = UUID(str(previous)),UUID(str(version))
    # Global administrative locks avoid account/player/content runtime lock
    # inversions. Controller must stop listener before this bounded operation.
    connection.execute(text('LOCK TABLE accounts,players,game_servers,content_versions,native_player_profiles,native_owned_roles,native_role_equipment,native_role_skills,native_map_progress,native_tutorial_claims,inventory_items IN SHARE ROW EXCLUSIVE MODE'))
    prepared = prepare_tutorial_release(connection,server_id,previous,source,disposable=disposable)
    if prepared['content_version_id']!=str(version):
        raise ValueError('explicit tutorial release ID mismatch')
    # This is not a general content migrator: deny if non-opening definitions or
    # inventory exist, and fail rather than strand any existing player assets.
    quote = connection.dialect.identifier_preparer.quote_identifier
    for table in connection.execute(text("SELECT table_name FROM information_schema.columns WHERE table_schema=current_schema() AND column_name='content_version_id'")).scalars():
        if table in {'native_player_content','native_player_profiles','native_owned_roles','command_receipts','reward_grants'}:
            continue
        if connection.execute(text(f'SELECT EXISTS(SELECT 1 FROM {quote(table)} WHERE content_version_id=:id)'),{'id':previous}).scalar_one():
            raise ValueError('non-opening content/assets require separately reviewed migration')
    players = connection.execute(text('SELECT p.id,n.content_version_id,n.rules_id,n.level,n.experience FROM players p LEFT JOIN native_player_profiles n ON n.player_id=p.id WHERE p.server_id=:server'),{'server':server_id}).mappings().all()
    old = connection.execute(text('SELECT rules_id,definitions,policy FROM native_player_content WHERE content_version_id=:id'),{'id':previous}).mappings().one()
    expected_equipment = [(1,slot,kind,1) for slot,kind in enumerate(old['definitions']['role']['initEvlItemIds'],1)]
    expected_skills = sorted((1,int(kind),group,level)
        for group,key in (('skills','skills'),('awakeSkills','awake_skills'))
        for kind,level in old['policy'][key].items())
    for player in players:
        if (player['content_version_id']!=previous or player['rules_id']!=old['rules_id'] or
                player['level']!=1 or player['experience']!=0):
            raise ValueError('existing profile incompatible with opening cutover')
        roles = connection.execute(text('SELECT slot,kind_id,content_version_id,star,level,experience,awake_level,awake_rate_increase_times FROM native_owned_roles WHERE player_id=:id'),{'id':player['id']}).mappings().all()
        if len(roles)!=1 or dict(roles[0])!={'slot':1,'kind_id':100101,'content_version_id':previous,'star':1,'level':1,'experience':0,'awake_level':0,'awake_rate_increase_times':0}:
            raise ValueError('existing roles incompatible with opening cutover')
        equipment = connection.execute(text('SELECT role_slot,equipment_slot,kind_id,level FROM native_role_equipment WHERE player_id=:id ORDER BY role_slot,equipment_slot'),{'id':player['id']}).all()
        if equipment!=expected_equipment:
            raise ValueError('existing equipment incompatible with opening cutover')
        skills = connection.execute(text('SELECT role_slot,kind_id,skill_group,level FROM native_role_skills WHERE player_id=:id ORDER BY role_slot,kind_id,skill_group,level'),{'id':player['id']}).all()
        if skills!=expected_skills:
            raise ValueError('existing skills incompatible with opening cutover')
        if connection.execute(text('SELECT EXISTS(SELECT 1 FROM native_map_progress WHERE player_id=:id) OR EXISTS(SELECT 1 FROM native_tutorial_claims WHERE player_id=:id)'),{'id':player['id']}).scalar_one():
            raise ValueError('existing progression or tutorial claims require separately reviewed migration')
        if connection.execute(text('SELECT EXISTS(SELECT 1 FROM inventory_items WHERE player_id=:id)'),{'id':player['id']}).scalar_one():
            raise ValueError('existing inventory requires separately reviewed migration')
    connection.execute(text("UPDATE content_versions SET status='PUBLISHED' WHERE id=:id AND status='DRAFT'"),{'id':version})
    connection.execute(text('UPDATE native_player_profiles SET content_version_id=:new WHERE player_id IN (SELECT id FROM players WHERE server_id=:server) AND content_version_id=:old'),{'new':version,'old':previous,'server':server_id})
    connection.execute(text('UPDATE native_owned_roles SET content_version_id=:new WHERE player_id IN (SELECT id FROM players WHERE server_id=:server) AND content_version_id=:old'),{'new':version,'old':previous,'server':server_id})
    connection.execute(text('UPDATE game_servers SET active_content_version_id=:new WHERE id=:server AND active_content_version_id=:old'),{'new':version,'old':previous,'server':server_id})
    return {'content_version_id':str(version),'migrated_players':len(players),'status':'PUBLISHED_NOT_NATIVE_CONFIRMED'}

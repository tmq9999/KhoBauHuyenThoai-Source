"""Stage pinned native starter definitions without executing JS or publishing."""
import hashlib
import json
from pathlib import Path

from sqlalchemy import text
from .source import read_table, read_table_archive

SOURCE_SHA = '9776b6e20978d5d911bc0abb85830820bac5a3bfb8db4e65a617c5d18646a818'
POLICY_KEYS = {'rules_id', 'origin', 'provenance', 'power_second_argument',
               'skills', 'awake_skills', 'skill_point_cap', 'hide_role_class_ids',
               'opening_state', 'owned_attribute_rule', 'recovery_policy', 'open_days'}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False)


def validate_policy(policy):
    if type(policy) is not dict or set(policy) != POLICY_KEYS:
        raise ValueError('explicit native player policy fields required: '+','.join(sorted(POLICY_KEYS)))
    for key, maximum in (('rules_id', 160), ('provenance', 2000)):
        if not isinstance(policy[key], str) or not policy[key].strip() or len(policy[key])>maximum:
            raise ValueError('native player policy requires rules identifier and provenance')
    if policy['origin'] != 'owner-approved-new-rule':
        raise ValueError('ambiguous native initialization requires owner-approved-new-rule')
    for key, minimum, maximum in (('power_second_argument',0,10000),('skill_point_cap',10,10000),('open_days',1,100000)):
        if type(policy[key]) is not int or not minimum <= policy[key] <= maximum:
            raise ValueError('invalid native player policy '+key)
    for key in ('skills','awake_skills'):
        if type(policy[key]) is not dict or len(policy[key])>20:
            raise ValueError('explicit owned skill maps required')
        if any(not isinstance(k,str) or not k.isascii() or not k.isdigit() or str(int(k))!=k or
               type(v) is not int or not 1 <= v <= 100 for k,v in policy[key].items()):
            raise ValueError('invalid initial owned skill level')
    if policy['awake_skills']:
        raise ValueError('awake skill initialization unsupported in native first slice')
    hidden = policy['hide_role_class_ids']
    if type(hidden) is not list or len(hidden)>1000 or any(type(v) is not int or not 0<v<=9007199254740991 for v in hidden) or len(set(hidden))!=len(hidden):
        raise ValueError('explicit hide role class policy required')
    if (policy['opening_state'] != 'unavailable-zero-v1' or
        policy['owned_attribute_rule'] != 'source-preview-floor-growth-v1' or
        policy['recovery_policy'] != 'source-300000ms-v1'):
        raise ValueError('unsupported explicit opening, attribute or recovery policy')
    return json.loads(canonical(policy))


def _selected_archive(source, sha, table, ids):
    archive = read_table_archive(source,sha,table)
    result = {}
    for cells in archive['rows']:
        if cells[0] not in ids:
            continue
        key = str(int(cells[0]))
        if key in result:
            raise ValueError('ambiguous native starter dependency')
        result[key] = dict(zip(archive['columns'],cells))
    if set(result) != {str(v) for v in ids}:
        raise ValueError('missing native starter dependency')
    return result


def read_native_player_content(source: Path, source_sha: str, policy: dict):
    policy = validate_policy(policy)
    if source_sha != SOURCE_SHA:
        raise ValueError('native player source pin mismatch')
    tables = {name: read_table(source,source_sha,name,allow_missing_trailing=True)
              for name in ('roleData','entityData','experienceData','evolutionItemData','soulData','vipData','friendshipData')}
    role = tables['roleData'][100101]
    equipment = role['initEvlItemIds']
    if len(equipment)!=6 or tables['entityData'][100101]['type']!='role':
        raise ValueError('invalid source starter role')
    # roleScene46465ff enumerates owned numeric keys, then appends source
    # skillIds starting at owned count. A non-prefix duplicates/omits skills.
    owned_skill_ids = sorted(int(v) for v in policy['skills'])
    if owned_skill_ids != role['skillIds'][:len(owned_skill_ids)]:
        raise ValueError('initial skills must be the source ordered prefix')
    souls = [r for r in tables['soulData'].values() if r.get('classId')==role['classId']]
    xp = [r for r in tables['experienceData'].values() if r.get('level')==1]
    vip = [r for r in tables['vipData'].values() if r.get('level')==0]
    if len(souls)!=1 or souls[0]['star']!=1 or len(xp)!=1 or len(vip)!=1:
        raise ValueError('ambiguous starter progression definition')
    classes = {r['classId'] for r in tables['roleData'].values()}
    referenced_classes = {v for row in tables['friendshipData'].values() for v in row['requiredClassIds']}
    hidden = set(policy['hide_role_class_ids'])
    if hidden-(classes|referenced_classes):
        raise ValueError('unknown hidden role class')
    # genFriendshipData55934 eagerly dereferences every referenced role,
    # including unavailable source class63. Hiding is an explicit policy
    # choice, never automatic sanitization of recovered source data.
    missing_classes = referenced_classes-classes
    if missing_classes-hidden:
        raise ValueError('native friendship requires explicit unavailable class policy: '+','.join(map(str,sorted(missing_classes-hidden))))
    for row in tables['friendshipData'].values():
        if hidden.intersection(row['requiredClassIds']):
            continue
        for class_id in row['requiredClassIds']:
            matching = [role for role in tables['roleData'].values() if role['classId']==class_id]
            if not matching or matching[0]['kindId'] not in tables['entityData']:
                raise ValueError('unresolved visible friendship role')
    skills = _selected_archive(source,source_sha,'fightSkillData',set(role['skillIds'])|{role['initSkillId']})
    # Only passive buffs affect first-home stat projection; battle effects are not simulated.
    buff_ids = {v for skill in skills.values() if skill['type']==3 for v in skill['buffIds']}
    buffs = _selected_archive(source,source_sha,'buffData',buff_ids)
    for buff in buffs.values():
        if (not buff.get('isAttacker') or not isinstance(buff.get('extra'),dict) or
            set(buff['extra'])-{'maxHp','hp','atk','def','mdef','crit','dodge','growth','symbol'} or
            buff['extra'].get('symbol')!='+'):
            raise ValueError('unsupported passive starter stats')
    return {'format':'native-player-content-v1','role':role,'entity':tables['entityData'][100101],
            'equipment':{str(v):tables['evolutionItemData'][v] for v in equipment},
            'soul':souls[0],'experience':xp[0],'vip':vip[0], 'skills':skills,'buffs':buffs,
            'friendship':{str(key):row for key,row in tables['friendshipData'].items()},
            'unavailable_role_classes':sorted(missing_classes)}


def prepare_native_player_content(connection, version, source, source_sha, policy):
    policy = validate_policy(policy)
    definitions = read_native_player_content(Path(source),source_sha,policy)
    digest = hashlib.sha256(canonical({'definitions':definitions,'policy':policy}).encode()).hexdigest()
    release = connection.execute(text('SELECT source_sha256,status FROM content_versions WHERE id=:id FOR UPDATE'),{'id':version}).mappings().one_or_none()
    if release is None or release['status']!='DRAFT' or release['source_sha256']!=source_sha:
        raise ValueError('native player definitions require existing matching DRAFT')
    saved = connection.execute(text('SELECT source_sha256,rules_id,definition_sha256,definitions,policy FROM native_player_content WHERE content_version_id=:id'),{'id':version}).mappings().one_or_none()
    expected = {'source_sha256':source_sha,'rules_id':policy['rules_id'],'definition_sha256':digest,'definitions':definitions,'policy':policy}
    if saved is not None:
        if dict(saved)!=expected:
            raise ValueError('native player content restage mismatch')
        return {'content_version_id':str(version),'definition_sha256':digest,'status':'DRAFT'}
    connection.execute(text('INSERT INTO native_player_content(content_version_id,source_sha256,rules_id,definition_sha256,definitions,policy) VALUES (:id,:source,:rules,:digest,CAST(:definitions AS jsonb),CAST(:policy AS jsonb))'),
        {'id':version,'source':source_sha,'rules':policy['rules_id'],'digest':digest,'definitions':canonical(definitions),'policy':canonical(policy)})
    return {'content_version_id':str(version),'definition_sha256':digest,'status':'DRAFT'}

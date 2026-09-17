"""Select source-backed combat dependency closure, never resolve duplicates silently."""
from collections import defaultdict, deque
import hashlib
from pathlib import Path

from .source import read_table_archive
from .native_players import SOURCE_SHA, canonical

TABLE_NAMES = {'smap':'smapData','bmap':'bmapData','mob':'mobData',
               'role':'roleData','entity':'entityData','fightSkill':'fightSkillData','buff':'buffData',
               'math':'mathData'}
CLIENT_LOOKUP_POLICY = 'vn-data-api-observed-lookup-v1'
_DUPLICATES = {
    ('fightSkill',1105010): [(466,'23de13cbc33f9bf7145e0b0c8c55ad9b7dc56881dd97ff3fc5cb503efc0bdad6'),
                           (467,'b948f90a0014333c6fa21c71638b5f10b729d7994b64d1d46a3269bd2245b4ce')],
    ('buff',10006): [(6,'2d5de81cdadfc6e58b38b3872a5ae4e6d8e2c86ee8ec3b98a951fbdea40f54c5'),
                    (7,'7b28ce5d2bd8db23761ee3ad5e7a58e4d78bb6c1dcc946981f9edfc1bc0fbd56')],
}


def battle_bundle(source: Path, map_ids: list[int], role_ids: list[int], *, lookup_policy: str | None = None) -> dict:
    """Trusted build-time API. Output is evidence, not approved reward rules.

    All source rows are retained in indexes until traversal selects one exact
    definition. Unrelated duplicates do not make an earlier unique map ambiguous;
    any reachable duplicate blocks unless its exact candidate fingerprints are
    explicitly resolved using the recorded client lookup compatibility policy.
    """
    if lookup_policy not in (None, CLIENT_LOOKUP_POLICY):
        raise ValueError('Unknown battle lookup policy')
    for name, values, bound in (('maps',map_ids,500),('roles',role_ids,100)):
        if (type(values) is not list or not 1 <= len(values) <= bound or
                any(type(v) is not int or not 0 < v <= 9007199254740991 for v in values) or
                len(set(values)) != len(values)):
            raise ValueError('Invalid battle '+name)
    indexes={}
    for short, table in TABLE_NAMES.items():
        archive=read_table_archive(source,SOURCE_SHA,table)
        index=defaultdict(list)
        for ordinal,cells in enumerate(archive['rows'],1):
            index[int(cells[0])].append((ordinal,dict(zip(archive['columns'],cells))))
        indexes[short]=index
    # battle.team generates the source ship sentinel even when ships=[] (truthy
    # in JavaScript); it is not player-owned ship inventory.
    queue=deque([('smap',v) for v in map_ids]+[('role',v) for v in role_ids]+[('mob',0)])
    selected={name:{} for name in TABLE_NAMES}
    origins={name:{} for name in TABLE_NAMES}
    resolutions=[]

    def ref(table,value,*,zero=False):
        if zero and value in (None,0): return
        if type(value) not in (int,float) or isinstance(value,bool) or int(value)!=value or not 0<value<=9007199254740991:
            raise ValueError('Invalid battle reference to '+table)
        queue.append((table,int(value)))

    def refs(table,values):
        if type(values) is not list: raise ValueError('Invalid battle reference list to '+table)
        for value in values: ref(table,value)

    while queue:
        table,key=queue.popleft()
        if str(key) in selected[table]: continue
        candidates=indexes[table].get(key,[])
        if len(candidates)>1 and lookup_policy == CLIENT_LOOKUP_POLICY:
            fingerprints=[(ordinal,hashlib.sha256(canonical(row).encode()).hexdigest()) for ordinal,row in candidates]
            if fingerprints != _DUPLICATES.get((table,key)):
                raise ValueError('Unreviewed battle duplicate '+table+':'+str(key))
            resolutions.append({'table':table,'kind_id':key,'policy':CLIENT_LOOKUP_POLICY,
                'source_consumer':'project.js:18445-18454','selected_row':candidates[-1][0],
                'candidates':[{'row':ordinal,'sha256':digest,'data':row}
                              for (ordinal,digest),(_,row) in zip(fingerprints,candidates)]})
            candidates=[candidates[-1]]
        if len(candidates)!=1:
            raise ValueError(('Ambiguous' if candidates else 'Missing')+' battle dependency '+table+':'+str(key))
        ordinal,row=candidates[0]
        selected[table][str(key)]=row
        origins[table][str(key)]=ordinal
        if table=='smap':
            ref('bmap',row.get('bmapId'))
            count=row.get('mobZoneCount')
            if type(count) is not int or not 1<=count<=2: raise ValueError('Unsupported battle wave count')
            for wave in range(1,count+1): refs('mob',row.get('mobZone'+str(wave)))
            if row['bmapId'] in (301,302): ref('fightSkill',100001 if row['bmapId']==301 else 100002)
        elif table=='role':
            ref('entity',key)
            ref('fightSkill',row.get('initSkillId'))
            refs('fightSkill',row.get('skillIds'))
        elif table=='mob':
            ref('fightSkill',row.get('initSkillId'))
            ids,levels=row.get('skillIds'),row.get('skillLevels')
            if type(ids) is not list or type(levels) is not list or len(levels)<len(ids):
                raise ValueError('Missing mob skill levels')
            if any(type(v) not in (int,float) or isinstance(v,bool) or v<0 or int(v)!=v for v in levels[:len(ids)]):
                raise ValueError('Invalid mob skill level')
            refs('fightSkill',ids)
        elif table=='fightSkill':
            refs('buff',row.get('buffIds'))
            if row.get('type')==4:
                target=row.get('atkPer')
                refs('mob',target if type(target) is list else [target])
        elif table=='buff':
            extra=row.get('extra')
            if type(extra) is not dict: raise ValueError('Invalid buff extra')
            if 'skillId' in extra: ref('fightSkill',extra['skillId'])
            for field,target in (('skillIds','fightSkill'),('buffIds','buff'),
                                 ('allowSkillIds','fightSkill'),('unAllowSkillIds','fightSkill')):
                if field in extra: refs(target,extra[field])
    # Formula queries by actor/target level at runtime. Preserve the entire
    # unique literal math level table rather than guessing mob/owned levels.
    levels=set()
    for key,candidates in indexes['math'].items():
        if len(candidates)!=1: raise ValueError('Ambiguous battle math row')
        ordinal,row=candidates[0]
        if row.get('level') in levels: raise ValueError('Ambiguous battle math level')
        levels.add(row.get('level'))
        selected['math'][str(key)]=row
        origins['math'][str(key)]=ordinal
    result={'format':'kbht-battle-content-v1','source_sha256':SOURCE_SHA,
            'map_ids':map_ids,'role_ids':role_ids,'tables':selected,'source_rows':origins,
            'lookup_policy':lookup_policy,'duplicate_resolutions':resolutions,
            'scope':'source reference closure only; no combat/reward publication'}
    result['content_sha256']=hashlib.sha256(canonical(result).encode()).hexdigest()
    return result

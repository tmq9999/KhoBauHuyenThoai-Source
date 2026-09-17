"""Stage verified fragment-only fixed boxes in an existing draft transaction."""
import json

from .source import read_table
from .acquisition import parse_drop_descriptor
from .validation import _integer


def stage_fixed_box(connection,content_version_id,kind_id,source,source_sha256):
    from sqlalchemy import text

    kind_id=_integer(kind_id,'box ID',1)
    entities=read_table(source,source_sha256,'entityData',allow_missing_trailing=True)
    box=entities.get(kind_id)
    if box is None or box.get('type')!='box':
        raise ValueError('unsupported fixed box')
    extra=box.get('extra')
    if not isinstance(extra,dict) or 'rdDropListDesc' in extra or 'dropListDesc' not in extra:
        raise ValueError('unsupported fixed box')
    rewards={}
    for entry in parse_drop_descriptor(extra['dropListDesc']):
        target=entry['entity_id']
        if entry['extra'] or entities.get(target,{}).get('type')!='fragment':
            raise ValueError('only fixed fragment rewards are supported')
        rewards[target]=_integer(rewards.get(target,0)+entry['quantity'],'reward total',1)
    if not rewards or len(rewards)>100:
        raise ValueError('unsupported fixed box reward count')
    params={'version':content_version_id,'kind':kind_id}
    version=connection.execute(text('SELECT source_sha256,status FROM content_versions WHERE id=:version FOR UPDATE'),params).one_or_none()
    if version is None or version[0]!=source_sha256.lower():
        raise ValueError('content source mismatch')
    if version[1]!='DRAFT':
        raise ValueError('fixed box staging requires DRAFT')
    required={kind_id,*rewards}
    definitions=set(connection.execute(text('SELECT kind_id FROM item_definitions WHERE content_version_id=:version'),params).scalars())
    if not required<=definitions:
        raise ValueError('missing item definition; explicit stack policy required')
    payload={'box':box,'rewards':{str(key):entities[key] for key in sorted(rewards)}}
    inserted=connection.execute(text(
        'INSERT INTO fixed_box_definitions(content_version_id,kind_id,source_payload) '
        'VALUES (:version,:kind,CAST(:payload AS jsonb)) ON CONFLICT DO NOTHING RETURNING kind_id'),
        {**params,'payload':json.dumps(payload,allow_nan=False)}).scalar_one_or_none()
    if inserted is not None:
        connection.execute(text('INSERT INTO fixed_box_rewards(content_version_id,kind_id,reward_kind_id,quantity) VALUES (:version,:kind,:reward,:quantity)'),
                           [{**params,'reward':key,'quantity':count} for key,count in sorted(rewards.items())])
    stored=connection.execute(text('SELECT source_payload FROM fixed_box_definitions WHERE content_version_id=:version AND kind_id=:kind'),params).scalar_one_or_none()
    lines=connection.execute(text('SELECT reward_kind_id,quantity FROM fixed_box_rewards WHERE content_version_id=:version AND kind_id=:kind ORDER BY reward_kind_id'),params).all()
    if stored!=payload or [tuple(line) for line in lines]!=sorted(rewards.items()):
        raise ValueError('fixed box projection mismatch')
    return {'kind_id':kind_id,'rewards':rewards}

"""Source-backed drop structure and material candidates, never a loot sampler."""
import math
import re

from .equipment import _acyclic, read_equipment_content
from .source import read_table
from .validation import _integer

FORMAT = 'material-acquisition-v1'
_FIXED = re.compile(r'([0-9]+)(?:_([A-Za-z][A-Za-z0-9]*)_([0-9]+))?x([0-9]+)')
_RANDOM = re.compile(r'([0-9]+)x([0-9]+)_([WR])([0-9]+(?:\.[0-9]+)?)')


def _positive_number(value):
    if type(value) not in (int,float) or not math.isfinite(value) or not 0 < value <= 2**53-1:
        raise ValueError('invalid drop weight/rate')
    return value


def parse_drop_descriptor(value: str, *, random: bool = False) -> list[dict]:
    """Parse the bounded client descriptor grammar; never ignore bad segments.

    W and R are preserved separately. R's probability scale and actual selection
    semantics are not inferred here. No expression or recovered JS is executed.
    """
    if not isinstance(value,str) or not value or len(value)>65536:
        raise ValueError('invalid drop descriptor')
    parts=value.split(',')
    if len(parts)>1000:
        raise ValueError('drop descriptor too large')
    result=[]
    for part in parts:
        match=(_RANDOM if random else _FIXED).fullmatch(part)
        if match is None:
            raise ValueError('invalid drop descriptor entry')
        if random:
            entity,count,kind,number=match.groups()
            number=float(number) if '.' in number else int(number)
            entry={'entity_id':_integer(int(entity),'entity ID',1),
                   'quantity':_integer(int(count),'quantity',1),'extra':{},
                   'weight' if kind=='W' else 'rate':_positive_number(number)}
        else:
            entity,field,extra,count=match.groups()
            entry={'entity_id':_integer(int(entity),'entity ID',1),
                   'quantity':_integer(int(count),'quantity',1),
                   'extra':{field:_integer(int(extra),'extra')} if field else {}}
        result.append(entry)
    return result


def acquisition_audit(entities: dict,drops: dict,normal_stages: dict,required_materials: list[int]) -> dict:
    """Validate references/cycles and list static candidates, not reachability."""
    for key,row in entities.items():
        if _integer(key,'entity ID',1)!=_integer(row.get('kindId'),'entity kindId',1):
            raise ValueError('entity identity mismatch')
    classes={_integer(row.get('classId'),'drop class',1) for row in drops.values()}
    edges={key:set() for key in classes}
    normalized=[]
    for key,row in sorted(drops.items()):
        if _integer(key,'drop ID',1)!=_integer(row.get('kindId'),'drop kindId',1):
            raise ValueError('drop identity mismatch')
        class_id=_integer(row.get('classId'),'drop class',1)
        group=_integer(row.get('groupId'),'drop group',1)
        reference=_integer(row.get('refClassId'),'referenced class')
        entity=_integer(row.get('entityId'),'drop entity')
        if bool(reference)==bool(entity):
            raise ValueError('drop requires exactly one target')
        if reference:
            if reference not in classes:
                raise ValueError('missing referenced drop class')
            edges[class_id].add(reference)
        elif entity not in entities:
            raise ValueError('missing drop entity')
        extra=row.get('extra')
        if not isinstance(extra,dict) and not (type(extra) is int and extra==0):
            raise ValueError('invalid drop extra')
        normalized.append({'kind_id':key,'class_id':class_id,'group_id':group,
                           'ref_class_id':reference,'entity_id':entity,
                           'weight':_positive_number(row.get('weight')),
                           'quantity':_integer(row.get('count'),'drop count'),
                           'extra':extra})
    _acyclic(edges)
    boxes=[]
    box_edges={key:set() for key,row in entities.items() if row.get('type')=='box'}
    for key in sorted(box_edges):
        extra=entities[key].get('extra')
        if not isinstance(extra,dict):
            continue
        fixed,random=extra.get('dropListDesc'),extra.get('rdDropListDesc')
        if fixed is not None and random is not None:
            raise ValueError('ambiguous box descriptor')
        if fixed is None and random is None:
            continue
        is_random=random is not None
        entries=parse_drop_descriptor(random if is_random else fixed,random=is_random)
        for entry in entries:
            target=entry['entity_id']
            if target not in entities:
                raise ValueError('missing box entity')
            if target in box_edges:
                box_edges[key].add(target)
        boxes.append({'box_id':key,'mode':'random' if is_random else 'fixed','entries':entries})
    _acyclic(box_edges)
    map_items={}
    for key,row in sorted(normal_stages.items()):
        if _integer(key,'map ID',1)!=_integer(row.get('kindId'),'map kindId',1):
            raise ValueError('map identity mismatch')
        repeatable=row.get('repeatable')
        if repeatable is not None and (type(repeatable) is not int or repeatable not in (0,1)):
            raise ValueError('invalid repeatable flag')
        ids=row.get('showEntityIds')
        if not isinstance(ids,list):
            raise ValueError('invalid map display list')
        for entity in ids:
            entity=_integer(entity,'displayed entity')
            if entity and entity not in entities:
                raise ValueError('missing map display entity')
            if entity and repeatable==1:
                map_items.setdefault(entity,set()).add(key)
    materials=[]
    for key in sorted(set(required_materials)):
        _integer(key,'material ID',1)
        if key not in entities:
            raise ValueError('missing required material')
        fixed=[box['box_id'] for box in boxes if box['mode']=='fixed' and any(e['entity_id']==key for e in box['entries'])]
        random=[box['box_id'] for box in boxes if box['mode']=='random' and any(e['entity_id']==key for e in box['entries'])]
        positive=[row['kind_id'] for row in normalized if row['entity_id']==key and row['quantity']>0]
        zero=[row['kind_id'] for row in normalized if row['entity_id']==key and row['quantity']==0]
        maps=sorted(map_items.get(key,()))
        materials.append({'entity_id':key,'repeatable_normal_maps':maps,
                          'fixed_boxes':fixed,'random_boxes':random,'positive_drop_rows':positive,
                          'zero_count_drop_rows':zero,
                          'status':'STATIC_CANDIDATES_ONLY' if maps or fixed or random or positive else 'NO_STATIC_CANDIDATE',
                          'gameplay_verified':False})
    return {'format':FORMAT,'publishable':False,'drop_rows':normalized,'boxes':boxes,
            'drop_class_edges':[[source,target] for source in sorted(edges) for target in sorted(edges[source])],
            'zero_count_rows':[row['kind_id'] for row in normalized if row['quantity']==0],
            'materials':materials,
            'pending':['class trigger/eligibility','zero-count semantics','R probability scale',
                       'normal specifyDropValues semantics','box acquisition','authoritative settlement','native acceptance']}


def read_acquisition_content(source,source_sha256):
    from .importer import import_release

    equipment=read_equipment_content(source,source_sha256)
    maps=import_release(source,source_sha256)
    stages={key:maps.smap[key] for key in maps.normal_maps}
    drops=read_table(source,source_sha256,'dropData')
    materials=[row['material_id'] for row in equipment['graph']['requirements']]
    sources={'entities':equipment['entities'],'recipes':equipment['recipes'],'drops':drops,'stages':stages}
    return {'format':FORMAT,'source_sha256':source_sha256.lower(),'sources':sources,
            'report':acquisition_audit(equipment['entities'],drops,stages,materials)}

"""Validated equipment content graphs; no inventory grants or gameplay commands."""
import math
from pathlib import Path

from .source import read_table
from .validation import _integer

FORMAT = 'equipment-draft-v1'


def _acyclic(edges: dict[int, set[int]]) -> None:
    # Iterative Kahn traversal avoids recursion limits on untrusted long chains.
    indegree = {key: 0 for key in edges}
    for targets in edges.values():
        for target in targets:
            indegree[target] += 1
    ready = [key for key, count in indegree.items() if count == 0]
    count = 0
    while ready:
        key = ready.pop()
        count += 1
        for target in edges[key]:
            indegree[target] -= 1
            if indegree[target] == 0:
                ready.append(target)
    if count != len(edges):
        raise ValueError('equipment recipe cycle')


def equipment_graph(entities: dict, recipes: dict) -> dict:
    if not recipes:
        raise ValueError('empty equipment content')
    definitions, requirements = [], []
    evolutions = {key: set() for key in recipes}
    materials = {key: set() for key in recipes}

    def entity(key):
        key = _integer(key, 'entity ID', 1)
        row = entities.get(key)
        if not isinstance(row, dict) or _integer(row.get('kindId'), 'entity kindId', 1) != key:
            raise ValueError('missing or mismatched equipment entity')
        return row

    for key, row in sorted(recipes.items()):
        _integer(key, 'equipment ID', 1)
        if _integer(row.get('kindId'), 'equipment kindId', 1) != key:
            raise ValueError('equipment kindId mismatch')
        if entity(key).get('type') != 'evolutionItem':
            raise ValueError('equipment entity type mismatch')
        effect = row.get('effect')
        if (not isinstance(effect, dict) or not effect or
                any(not isinstance(name, str) or not name or type(value) not in (int,float)
                    or not math.isfinite(value) or abs(value)>2**53-1
                    for name,value in effect.items())):
            raise ValueError('invalid equipment effect')
        target = row.get('evolutionItemId')
        if target is not None:
            target = _integer(target, 'next equipment ID') or None
            if target is not None and target not in recipes:
                raise ValueError('missing next equipment')
            if target is not None:
                evolutions[key].add(target)
        definitions.append({'kind_id':key,'next_kind_id':target,'effect':dict(effect)})
        ids, counts = row.get('requiredIds'), row.get('requiredCounts')
        if ids is None and counts is None:
            ids, counts = [], []
        if not isinstance(ids,list) or not isinstance(counts,list) or len(ids)!=len(counts):
            raise ValueError('invalid equipment recipe shape')
        seen = set()
        for position,(material,quantity) in enumerate(zip(ids,counts),1):
            material = _integer(material,'material ID',1)
            quantity = _integer(quantity,'material quantity',1)
            entity(material)
            if material in seen:
                raise ValueError('duplicate recipe material')
            seen.add(material)
            if material in recipes:
                materials[key].add(material)
            requirements.append({'kind_id':key,'position':position,
                                 'material_id':material,'quantity':quantity})
    _acyclic(evolutions)
    _acyclic(materials)
    return {'definitions':definitions,'requirements':requirements}


def read_equipment_content(source: Path, source_sha256: str) -> dict:
    entities = read_table(source, source_sha256, 'entityData', allow_missing_trailing=True)
    recipes = read_table(source, source_sha256, 'evolutionItemData')
    return {'format':FORMAT,'source_sha256':source_sha256.lower(),
            'entities':entities,'recipes':recipes,'graph':equipment_graph(entities,recipes)}

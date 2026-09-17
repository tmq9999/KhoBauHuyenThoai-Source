"""Ordered evidence archives and bounded reference audit; never gameplay rules."""
from collections import defaultdict, deque
from pathlib import Path

from .source import read_table_archive
from .validation import _integer

TABLES = ('mobData', 'fightSkillData', 'buffData', 'entityData',
          'evolutionItemData', 'consumablesData', 'dropData')
FORMAT = 'normal-dependency-audit-v1'


def read_dependency_bundle(source: Path, source_sha256: str) -> dict:
    from .importer import import_release

    release = import_release(source, source_sha256)
    tables = {name: read_table_archive(source, source_sha256, name) for name in TABLES}
    return {'format': FORMAT, 'source_sha256': source_sha256.lower(), 'tables': tables,
            'report': audit_dependencies(release.normal_maps, release.smap, tables)}


def audit_dependencies(normal_maps: dict, smap: dict, tables: dict) -> dict:
    """Audit normal mobs and transitive skills/buffs, plus item recipe references.

    Duplicate definitions are archived and reported, never resolved by last-wins.
    CHECKED means only the named reference surfaces passed, not combat validity.
    """
    issues, edges, mob_skills = [], [], []
    indexes, ambiguous = {}, {}
    for name in TABLES:
        table = tables[name]
        grouped = defaultdict(list)
        for ordinal, cells in enumerate(table['rows'], 1):
            grouped[int(cells[0])].append((ordinal, dict(zip(table['columns'], cells))))
        ambiguous[name] = {key for key, rows in grouped.items() if len(rows) > 1}
        indexes[name] = {key: rows[0][1] for key, rows in grouped.items() if len(rows) == 1}
        for key in sorted(ambiguous[name]):
            issues.append({'code': 'DUPLICATE_ID', 'table': name, 'kind_id': key,
                           'rows': [ordinal for ordinal, _ in grouped[key]]})

    queue, visited = deque(), set()

    def issue(code, table, key, field=None):
        item = {'code': code, 'table': table, 'kind_id': key}
        if field is not None:
            item['field'] = field
        if item not in issues:
            issues.append(item)

    def ref(owner_table, owner_id, field, target, key, *, zero=False):
        try:
            key = _integer(key, field)
            if key == 0 and zero:
                return
            if key == 0:
                raise ValueError('zero reference')
        except ValueError:
            issue('INVALID_REFERENCE', owner_table, owner_id, field)
            return
        edges.append([owner_table, owner_id, field, target, key])
        queue.append((target, key))

    def refs(owner, key, field, target, values, *, zero=False):
        if not isinstance(values, list):
            issue('INVALID_REFERENCE_LIST', owner, key, field)
            return
        for value in values:
            ref(owner, key, field, target, value, zero=zero)

    for map_id, row in sorted(normal_maps.items()):
        for wave in row['waves']:
            refs('smapData', map_id, 'waves', 'mobData', wave)
        for field in ('showEntityIds', 'specifyDropEntityIds'):
            refs('smapData', map_id, field, 'entityData', smap[map_id].get(field), zero=True)
    # All equipment recipes/consumables are independently useful content inputs.
    for name in ('evolutionItemData', 'consumablesData'):
        queue.extend((name, key) for key in sorted(indexes[name]))

    while queue:
        name, key = queue.popleft()
        if (name, key) in visited:
            continue
        visited.add((name, key))
        if key in ambiguous[name]:
            issue('AMBIGUOUS_REFERENCE', name, key)
            continue
        row = indexes[name].get(key)
        if row is None:
            issue('MISSING_REFERENCE', name, key)
            continue
        if name == 'mobData':
            ref(name, key, 'initSkillId', 'fightSkillData', row.get('initSkillId'))
            try:
                initial = _integer(row.get('initSkillId'), 'initSkillId', 1)
                ids, levels = row.get('skillIds'), row.get('skillLevels')
                if not isinstance(ids, list) or not isinstance(levels, list) or len(levels) < len(ids):
                    raise ValueError('missing consumed level')
                consumed = [(_integer(skill, 'skillId', 1), _integer(levels[pos], 'skillLevel'))
                            for pos, skill in enumerate(ids)]
                mob_skills.append([key, 0, initial, 0])
                for pos, (skill, level) in enumerate(consumed, 1):
                    mob_skills.append([key, pos, skill, level])
                    ref(name, key, 'skillIds', 'fightSkillData', skill)
            except ValueError:
                issue('INVALID_MOB_SKILLS', name, key)
        elif name == 'fightSkillData':
            refs(name, key, 'buffIds', 'buffData', row.get('buffIds'))
            if row.get('type') == 4:  # battle.fightHandler.summon uses atkPer as mob IDs
                values = row.get('atkPer')
                refs(name, key, 'atkPer', 'mobData', values if isinstance(values, list) else [values])
        elif name == 'buffData':
            extra = row.get('extra')
            if not isinstance(extra, dict):
                issue('INVALID_EXTRA', name, key)
                continue
            if 'skillId' in extra:
                ref(name, key, 'extra.skillId', 'fightSkillData', extra['skillId'])
            for field, target in (('skillIds','fightSkillData'), ('buffIds','buffData'),
                                  ('allowSkillIds','fightSkillData'), ('unAllowSkillIds','fightSkillData')):
                if field in extra:
                    refs(name, key, 'extra.' + field, target, extra[field])
        elif name in ('evolutionItemData', 'consumablesData'):
            ref(name, key, 'kindId', 'entityData', key)
            if name == 'evolutionItemData':
                ids, counts = row.get('requiredIds'), row.get('requiredCounts')
                if ids is None and counts is None:
                    ids, counts = [], []  # base recipe has no ingredients
                try:
                    if not isinstance(ids, list) or not isinstance(counts, list) or len(ids) != len(counts):
                        raise ValueError('recipe shape')
                    for count in counts:
                        _integer(count, 'requiredCount', 1)
                    refs(name, key, 'requiredIds', 'entityData', ids)
                except ValueError:
                    issue('INVALID_RECIPE', name, key)
                target = row.get('evolutionItemId')
                if target is not None:
                    ref(name, key, 'evolutionItemId', 'evolutionItemData', target, zero=True)

    return {'format': FORMAT, 'reference_status': 'BLOCKED' if issues else 'CHECKED',
            'publishable': False, 'counts': {name: len(tables[name]['rows']) for name in TABLES},
            'issues': issues, 'edges': edges, 'mob_skills': sorted(mob_skills),
            'scope': 'normal-map mob/skill/buff closure; displayed entities; equipment recipe references',
            'pending': ['duplicate policy', 'combat numeric/effect semantics', 'drop interpretation',
                        'recipe cycles/acquisition', 'other modes', 'native acceptance']}

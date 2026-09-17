import sys
from copy import deepcopy
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'server-online/src'))
from kbht_server.content import importer


def archive(columns, *rows):
    return {'columns': ['kindId', *columns], 'rows': list(rows)}


def tables():
    return {
        'mobData': archive(['initSkillId','skillIds','skillLevels'], [31,100,[101],[2,9]]),
        'fightSkillData': archive(['buffIds','type','atkPer'], [100,[],1,1], [101,[201],1,1], [102,[],1,1]),
        'buffData': archive(['extra'], [201,{'skillId':102}]),
        'entityData': archive(['type'], [41,'fragment']),
        'evolutionItemData': archive(['requiredIds','requiredCounts','evolutionItemId']),
        'consumablesData': archive(['roleExp','actionPoint']),
        'dropData': archive(['classId','refClassId','entityId']),
    }


def audit(data):
    assert hasattr(importer, 'audit_dependencies'), 'dependency audit missing'
    return importer.audit_dependencies({7:{'waves':[[31]]}},
        {7:{'showEntityIds':[41,0], 'specifyDropEntityIds':[41,0]}}, data)


def test_transitive_buff_skill_reference_is_audited_and_extra_levels_preserved():
    data = tables()
    report = audit(data)
    assert report['reference_status'] == 'CHECKED'
    assert report['publishable'] is False
    assert ['buffData',201,'extra.skillId','fightSkillData',102] in report['edges']
    assert report['mob_skills'] == [[31,0,100,0], [31,1,101,2]]
    assert data['mobData']['rows'][0][3] == [2,9]


@pytest.mark.parametrize('table,key,code', [
    ('mobData',31,'MISSING_REFERENCE'), ('fightSkillData',102,'MISSING_REFERENCE'),
    ('buffData',201,'MISSING_REFERENCE'), ('entityData',41,'MISSING_REFERENCE'),
])
def test_missing_reachable_dependency_blocks(table,key,code):
    data = tables()
    data[table]['rows'] = [row for row in data[table]['rows'] if row[0] != key]
    result = audit(data)
    assert result['reference_status'] == 'BLOCKED'
    assert any(issue['code']==code and issue['table']==table and issue['kind_id']==key for issue in result['issues'])


def test_duplicate_child_definition_not_silently_last_wins():
    data = tables()
    data['fightSkillData']['rows'].append([102,[],2,99])
    report = audit(data)
    assert report['reference_status'] == 'BLOCKED'
    assert {'code':'DUPLICATE_ID','table':'fightSkillData','kind_id':102,'rows':[3,4]} in report['issues']
    assert report['counts']['fightSkillData'] == 4


@pytest.mark.parametrize('levels', [[],[True],[-1]])
def test_missing_or_invalid_consumed_skill_level_blocks(levels):
    data = tables()
    data['mobData']['rows'][0][3] = levels
    assert any(issue['code']=='INVALID_MOB_SKILLS' for issue in audit(data)['issues'])


def test_summoned_mob_and_recursive_buffs_are_traversed_without_loop():
    data = tables()
    data['fightSkillData']['rows'][2] = [102,[201],4,32]
    data['mobData']['rows'].append([32,100,[],[]])
    result = audit(data)
    assert result['reference_status'] == 'CHECKED'
    assert ['fightSkillData',102,'atkPer','mobData',32] in result['edges']


def test_missing_recipe_item_blocks_without_inventing_reward():
    data = tables()
    data['entityData']['rows'].append([50,'evolutionItem'])
    data['evolutionItemData']['rows'].append([50,[999],[2],0])
    result = audit(data)
    assert any(issue['table']=='entityData' and issue['kind_id']==999 for issue in result['issues'])


def test_real_apk_audit_preserves_conflicting_definitions():
    assert hasattr(importer, 'read_dependency_bundle'), 'dependency bundle missing'
    root = Path(__file__).resolve().parents[2]
    result = importer.read_dependency_bundle(root/'client-recovered/src/project.js',
        '9776b6e20978d5d911bc0abb85830820bac5a3bfb8db4e65a617c5d18646a818')
    assert result['report']['counts'] == {
        'mobData':16245,'fightSkillData':474,'buffData':745,'entityData':1812,
        'evolutionItemData':120,'consumablesData':7,'dropData':379}
    assert result['report']['reference_status'] == 'BLOCKED'
    assert result['report']['publishable'] is False
    assert any(i['code']=='DUPLICATE_ID' and i['kind_id']==1105010 for i in result['report']['issues'])
    assert any(i['code']=='DUPLICATE_ID' and i['kind_id']==10006 for i in result['report']['issues'])
    assert ['buffData',210902,'extra.skillId','fightSkillData',1109010] in result['report']['edges']
    assert [1010711,1,110901,2] in result['report']['mob_skills']
    assert len([row for row in result['tables']['fightSkillData']['rows'] if row[0]==1105010]) == 2

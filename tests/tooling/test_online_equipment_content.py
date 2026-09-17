import sys
from copy import deepcopy
from pathlib import Path

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'server-online/src'))
from kbht_server.content import importer


def inputs():
    entities={1:{'kindId':1,'type':'evolutionItem'},2:{'kindId':2,'type':'evolutionItem'},
              9:{'kindId':9,'type':'fragment'}}
    recipes={1:{'kindId':1,'effect':{'initHp':10},'requiredIds':None,'requiredCounts':None,'evolutionItemId':2},
             2:{'kindId':2,'effect':{'initHp':20},'requiredIds':[9],'requiredCounts':[3],'evolutionItemId':None}}
    return entities,recipes


def project(entities,recipes):
    assert hasattr(importer,'equipment_graph'),'equipment graph missing'
    return importer.equipment_graph(entities,recipes)


def test_target_recipe_contains_cost_not_source_recipe():
    entities,recipes=inputs()
    before=deepcopy(recipes)
    result=project(entities,recipes)
    assert result['definitions']==[
        {'kind_id':1,'next_kind_id':2,'effect':{'initHp':10}},
        {'kind_id':2,'next_kind_id':None,'effect':{'initHp':20}}]
    assert result['requirements']==[{'kind_id':2,'position':1,'material_id':9,'quantity':3}]
    assert recipes==before


@pytest.mark.parametrize('mutation',[
    'cycle','self','missing_next','missing_entity','wrong_type','missing_material',
    'short_counts','empty_counts','negative','bool_quantity','fraction','duplicate_material',
    'bad_effect','infinite_effect','bool_effect','wrong_identity','bool_next',
])
def test_invalid_equipment_graph_rejected(mutation):
    entities,recipes=inputs()
    if mutation=='cycle': recipes[2]['evolutionItemId']=1
    elif mutation=='self': recipes[1]['evolutionItemId']=1
    elif mutation=='missing_next': recipes[1]['evolutionItemId']=3
    elif mutation=='missing_entity': del entities[2]
    elif mutation=='wrong_type': entities[2]['type']='fragment'
    elif mutation=='missing_material': del entities[9]
    elif mutation=='short_counts': recipes[2]['requiredCounts']=[]
    elif mutation=='empty_counts': recipes[2]['requiredCounts']=None
    elif mutation=='negative': recipes[2]['requiredCounts']=[-1]
    elif mutation=='bool_quantity': recipes[2]['requiredCounts']=[True]
    elif mutation=='fraction': recipes[2]['requiredCounts']=[1.5]
    elif mutation=='duplicate_material': recipes[2].update(requiredIds=[9,9],requiredCounts=[1,2])
    elif mutation=='bad_effect': recipes[2]['effect']=None
    elif mutation=='infinite_effect': recipes[2]['effect']={'initHp':float('inf')}
    elif mutation=='bool_effect': recipes[2]['effect']={'initHp':True}
    elif mutation=='wrong_identity': recipes[2]['kindId']=3
    elif mutation=='bool_next': recipes[1]['evolutionItemId']=True
    with pytest.raises(ValueError): project(entities,recipes)


def test_material_dependency_cycle_rejected():
    entities,recipes=inputs()
    recipes[1].update(requiredIds=[2],requiredCounts=[1])
    recipes[2].update(requiredIds=[1],requiredCounts=[1])
    with pytest.raises(ValueError,match='cycle'): project(entities,recipes)


def test_zero_terminal_sentinel_is_not_a_missing_equipment():
    entities,recipes=inputs()
    recipes[2]['evolutionItemId']=0
    assert project(entities,recipes)['definitions'][1]['next_kind_id'] is None


def test_pinned_equipment_chain_and_green_material_cost():
    assert hasattr(importer,'read_equipment_content'),'equipment content reader missing'
    result=importer.read_equipment_content(Path(__file__).resolve().parents[2]/'client-recovered/src/project.js',
        '9776b6e20978d5d911bc0abb85830820bac5a3bfb8db4e65a617c5d18646a818')
    graph=result['graph']
    assert len(graph['definitions'])==120
    assert len(graph['requirements'])==342
    assert next(row for row in graph['definitions'] if row['kind_id']==30101)['next_kind_id']==30102
    assert [row for row in graph['requirements'] if row['kind_id']==30102]==[
        {'kind_id':30102,'position':1,'material_id':40102,'quantity':1},
        {'kind_id':30102,'position':2,'material_id':42102,'quantity':1},
        {'kind_id':30102,'position':3,'material_id':49902,'quantity':1}]
    assert result['entities'][30102]['maxNum']==-1
    assert next(row for row in graph['definitions'] if row['kind_id']==30120)['next_kind_id'] is None

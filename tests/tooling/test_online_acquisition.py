import sys
from pathlib import Path

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'server-online/src'))
from kbht_server.content import importer


def parse(value, random=False):
    assert hasattr(importer,'parse_drop_descriptor'),'drop descriptor parser missing'
    return importer.parse_drop_descriptor(value,random=random)


def test_fixed_descriptor_preserves_extra_and_exact_counts():
    assert parse('49902x6,100201_star_2x1')==[
        {'entity_id':49902,'quantity':6,'extra':{}},
        {'entity_id':100201,'quantity':1,'extra':{'star':2}}]


def test_random_descriptor_preserves_weight_vs_rate_without_sampling():
    assert parse('60101x1_W10,60102x2_R0.5',True)==[
        {'entity_id':60101,'quantity':1,'extra':{},'weight':10},
        {'entity_id':60102,'quantity':2,'extra':{},'rate':0.5}]


@pytest.mark.parametrize('value,random',[
    ('',False),('49902x0',False),('49902x-1',False),('49902x1.5',False),
    ('truex1',False),('1x9007199254740992',False),('1x1,garbage',False),
    ('1x1_RNaN',True),('1x1_W0',True),('1x1_W-1',True),('1x1_R1e999',True),
    ('1x1_W1junk',True),('1x1;run()',False),('1_star_2_morex1',False),
])
def test_invalid_descriptor_fails_instead_of_silent_partial_reward(value,random):
    with pytest.raises(ValueError): parse(value,random)


def fixtures():
    entities={9:{'kindId':9,'type':'fragment'},10:{'kindId':10,'type':'box','extra':{'dropListDesc':'9x6'}}}
    drops={1:{'kindId':1,'classId':100,'groupId':1,'refClassId':200,'entityId':0,'weight':10,'count':1,'extra':0},
           2:{'kindId':2,'classId':200,'groupId':1,'refClassId':0,'entityId':9,'weight':2,'count':3,'extra':0}}
    return entities,drops


def audit(entities,drops,stages=None):
    assert hasattr(importer,'acquisition_audit'),'acquisition validator missing'
    return importer.acquisition_audit(entities,drops,stages or {},[9])


def test_candidates_are_not_claimed_as_playable_acquisition():
    entities,drops=fixtures()
    result=audit(entities,drops,{77:{'kindId':77,'repeatable':1,'showEntityIds':[9,0]}})
    material=result['materials'][0]
    assert material=={'entity_id':9,'repeatable_normal_maps':[77],'fixed_boxes':[10],
                      'random_boxes':[],'positive_drop_rows':[2],'zero_count_drop_rows':[],
                      'status':'STATIC_CANDIDATES_ONLY','gameplay_verified':False}
    assert result['publishable'] is False
    assert result['drop_class_edges']==[[100,200]]


@pytest.mark.parametrize('change',['cycle','missing_class','missing_entity','both','neither','bool_weight','negative_count','fraction_count','wrong_id','bad_extra','missing_box_item','box_cycle'])
def test_bad_drop_or_box_graph_is_rejected(change):
    entities,drops=fixtures()
    if change=='cycle': drops[2].update(refClassId=100,entityId=0)
    elif change=='missing_class': drops[1]['refClassId']=999
    elif change=='missing_entity': del entities[9]
    elif change=='both': drops[1]['entityId']=9
    elif change=='neither': drops[2]['entityId']=0
    elif change=='bool_weight': drops[2]['weight']=True
    elif change=='negative_count': drops[2]['count']=-1
    elif change=='fraction_count': drops[2]['count']=0.5
    elif change=='wrong_id': drops[2]['kindId']=3
    elif change=='bad_extra': drops[2]['extra']='script'
    elif change=='missing_box_item': entities[10]['extra']['dropListDesc']='999x1'
    elif change=='box_cycle': entities[10]['extra']['dropListDesc']='10x1'
    with pytest.raises(ValueError): audit(entities,drops)


def test_zero_count_and_nonrepeatable_preview_are_not_positive_sources():
    entities,drops=fixtures()
    del entities[10]
    drops[2]['count']=0
    result=audit(entities,drops,{77:{'kindId':77,'repeatable':0,'showEntityIds':[9]}})
    assert result['materials'][0]['status']=='NO_STATIC_CANDIDATE'
    assert result['materials'][0]['zero_count_drop_rows']==[2]
    assert result['zero_count_rows']==[2]


def test_real_green_material_source_evidence_not_fake_map_loot():
    assert hasattr(importer,'read_acquisition_content'),'source-backed acquisition missing'
    result=importer.read_acquisition_content(Path(__file__).resolve().parents[2]/'client-recovered/src/project.js',
        '9776b6e20978d5d911bc0abb85830820bac5a3bfb8db4e65a617c5d18646a818')
    report=result['report']
    material=next(row for row in report['materials'] if row['entity_id']==49902)
    assert material['repeatable_normal_maps']==[]
    assert material['fixed_boxes']==[321]
    assert material['positive_drop_rows']==[10010,10054,10113,10115,10118]
    assert material['gameplay_verified'] is False and report['publishable'] is False
    assert len(report['zero_count_rows'])==177
    assert len(result['sources']['drops'])==379
    assert result['sources']['stages'][10107]['specifyDropValues']==[125,125,125]

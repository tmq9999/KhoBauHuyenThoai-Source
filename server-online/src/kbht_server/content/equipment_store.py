"""Atomic equipment-only DRAFT projections, never publication or inventory."""
import hashlib
import json
from uuid import NAMESPACE_URL,uuid5

from .equipment import read_equipment_content


def prepare_equipment_draft(engine,source,source_sha256):
    from sqlalchemy import text

    bundle=read_equipment_content(source,source_sha256)
    encoded=json.dumps(bundle,sort_keys=True,separators=(',',':'),allow_nan=False)
    digest=hashlib.sha256(encoded.encode()).hexdigest()
    version_id=uuid5(NAMESPACE_URL,f"kbht:equipment:{bundle['source_sha256']}:{digest}")
    graph=bundle['graph']
    entity_ids={row['kind_id'] for row in graph['definitions']} | {row['material_id'] for row in graph['requirements']}
    definitions=[{'content_version_id':version_id,**row} for row in graph['definitions']]
    requirements=[{'content_version_id':version_id,**row} for row in graph['requirements']]
    entities=[{'content_version_id':version_id,'kind_id':key,'payload':bundle['entities'][key]} for key in sorted(entity_ids)]
    with engine.begin() as connection:
        inserted=connection.execute(text(
            "INSERT INTO content_versions(id,source_sha256,rules_sha256,status) VALUES (:id,:sha,:digest,'DRAFT') "
            "ON CONFLICT DO NOTHING RETURNING id"),{'id':version_id,'sha':bundle['source_sha256'],'digest':digest}).scalar_one_or_none()
        stored=connection.execute(text('SELECT source_sha256,rules_sha256,status FROM content_versions WHERE id=:id FOR UPDATE'),{'id':version_id}).one()
        if tuple(stored)!=(bundle['source_sha256'],digest,'DRAFT'):
            raise ValueError('equipment version mismatch')
        if inserted is not None:
            connection.execute(text('INSERT INTO equipment_source_snapshots(content_version_id,payload) VALUES (:id,CAST(:payload AS jsonb))'),{'id':version_id,'payload':encoded})
        saved=connection.execute(text('SELECT payload FROM equipment_source_snapshots WHERE content_version_id=:id'),{'id':version_id}).scalar_one_or_none()
        if saved!=json.loads(encoded):
            raise ValueError('equipment source mismatch')
        for table,rows,json_column,order in (
            ('equipment_entities',entities,'payload','kind_id'),
            ('equipment_definitions',definitions,'effect','kind_id'),
            ('equipment_requirements',requirements,None,'kind_id,position'),
        ):
            if inserted is not None and rows:
                columns=list(rows[0])
                values=[f'CAST(:{col} AS jsonb)' if col==json_column else ':'+col for col in columns]
                parameters=[{col:json.dumps(value,allow_nan=False) if col==json_column else value for col,value in row.items()} for row in rows]
                connection.execute(text(f"INSERT INTO {table} ({','.join(columns)}) VALUES ({','.join(values)})"),parameters)
            actual=connection.execute(text(f'SELECT * FROM {table} WHERE content_version_id=:id ORDER BY {order}'),{'id':version_id}).mappings().all()
            if [dict(row) for row in actual]!=rows:
                raise ValueError('equipment projection mismatch')
    return {'id':version_id,'status':'DRAFT','publishable':False,'format':bundle['format'],
            'source_sha256':bundle['source_sha256'],'rules_sha256':digest,
            'equipment_count':len(definitions),'requirement_count':len(requirements)}

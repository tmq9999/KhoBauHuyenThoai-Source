"""Persist blocked or checked evidence without publishing gameplay content."""
import hashlib
import json
from uuid import NAMESPACE_URL, uuid5

from .dependencies import read_dependency_bundle


def store_dependencies(engine, source, source_sha256):
    bundle = read_dependency_bundle(source, source_sha256)
    identity = _store_bundle(engine,bundle)
    report = bundle['report']
    return {**identity, 'reference_status': report['reference_status'],
            'publishable': False, 'counts': report['counts'], 'issues': report['issues']}


def store_acquisition(engine,source,source_sha256):
    from .acquisition import read_acquisition_content

    bundle=read_acquisition_content(source,source_sha256)
    identity=_store_bundle(engine,bundle)
    report=bundle['report']
    return {**identity,'publishable':False,'materials':report['materials'],
            'zero_count_rows':len(report['zero_count_rows']),
            'drop_row_count':len(report['drop_rows']),'box_count':len(report['boxes']),
            'pending':report['pending']}


def _store_bundle(engine,bundle):
    from sqlalchemy import text

    encoded = json.dumps(bundle, sort_keys=True, separators=(',', ':'), allow_nan=False)
    # JSONB object keys are strings. Compare canonical JSON semantics rather than
    # Python's integer-keyed source dictionaries on exact replay.
    expected = json.loads(encoded)
    digest = hashlib.sha256(encoded.encode()).hexdigest()
    archive_id = uuid5(NAMESPACE_URL, f"kbht:dependency:{bundle['source_sha256']}:{bundle['format']}")
    params = {'id': archive_id, 'sha': bundle['source_sha256'], 'format': bundle['format'],
              'digest': digest, 'bundle': encoded}
    with engine.begin() as connection:
        connection.execute(text(
            'INSERT INTO content_dependency_archives(id,source_sha256,format,bundle_sha256,bundle) '
            'VALUES (:id,:sha,:format,:digest,CAST(:bundle AS jsonb)) '
            'ON CONFLICT DO NOTHING'), params)
        stored = connection.execute(text(
            'SELECT id,bundle_sha256,bundle FROM content_dependency_archives '
            'WHERE source_sha256=:sha AND format=:format'), params).one_or_none()
        if stored is None or tuple(stored) != (archive_id, digest, expected):
            raise ValueError('dependency archive mismatch')
    return {'id': archive_id, 'source_sha256': bundle['source_sha256'], 'format': bundle['format'],
            'bundle_sha256': digest}

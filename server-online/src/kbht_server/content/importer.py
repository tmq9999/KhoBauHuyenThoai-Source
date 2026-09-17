"""Stage source-verified APK rows, without publishing gameplay rules."""
from dataclasses import dataclass
from uuid import UUID, uuid5, NAMESPACE_URL
import hashlib
import json
from pathlib import Path
from typing import Any
from .source import read_table
from .validation import normal_map_graph
from .dependencies import audit_dependencies, read_dependency_bundle
from .archive import store_dependencies, store_acquisition
from .equipment import equipment_graph, read_equipment_content
from .equipment_store import prepare_equipment_draft
from .acquisition import parse_drop_descriptor, acquisition_audit, read_acquisition_content
from .fixed_boxes import stage_fixed_box

@dataclass(frozen=True)
class ContentRelease:
    source_sha256: str
    smap: dict[int, dict[str, Any]]
    bmap: dict[int, dict[str, Any]]
    normal_maps: dict[int, dict[str, Any]]

def import_release(source: Path, source_sha256: str) -> ContentRelease:
    smap = read_table(source, source_sha256, "smapData")
    if not smap:
        raise ValueError("content source has no maps")
    for map_id, row in smap.items():
        if row.get("kindId") != map_id:
            raise ValueError("map kindId mismatch")
    bmap = read_table(source, source_sha256, "bmapData", allow_missing_trailing=True)
    return ContentRelease(source_sha256.lower(), smap, bmap, normal_map_graph(bmap, smap))

def store_source(engine, source: Path, source_sha256: str) -> dict[str, Any]:
    from sqlalchemy import text

    release = import_release(source, source_sha256)
    with engine.begin() as connection:
        existing = connection.execute(text("SELECT id, status, row_count FROM content_source_imports WHERE source_sha256=:sha"), {"sha": release.source_sha256}).mappings().first()
        if existing:
            _store_chapters(connection, existing["id"], release)
            return {"id": existing["id"], "status": existing["status"], "rows": existing["row_count"]}
        inserted = connection.execute(text(
            "INSERT INTO content_source_imports(id,source_sha256,table_name,status,row_count) "
            "VALUES (gen_random_uuid(),:sha,'smapData','STAGED',:count) "
            "ON CONFLICT (source_sha256) DO NOTHING RETURNING id"
        ), {"sha": release.source_sha256, "count": len(release.smap)}).scalar_one_or_none()
        if inserted is None:
            existing = connection.execute(text(
                "SELECT id, status, row_count FROM content_source_imports WHERE source_sha256=:sha"
            ), {"sha": release.source_sha256}).mappings().one()
            _store_chapters(connection, existing["id"], release)
            return {"id": existing["id"], "status": existing["status"], "rows": existing["row_count"]}
        import_id = inserted
        connection.execute(text(
            "INSERT INTO content_source_rows(import_id,kind_id,payload) VALUES (:id,:kind,CAST(:payload AS jsonb))"
        ), [{"id": import_id, "kind": kind_id, "payload": json.dumps(row, allow_nan=False)}
            for kind_id, row in release.smap.items()])
        _store_chapters(connection, import_id, release)
    return {"id": import_id, "status": "STAGED", "rows": len(release.smap)}


def _store_chapters(connection, import_id: UUID, release: ContentRelease) -> None:
    from sqlalchemy import text

    connection.execute(text("SELECT id FROM content_source_imports WHERE id=:id FOR UPDATE"), {"id": import_id})
    # Backfill old smap-only imports only after their saved source rows agree.
    saved = connection.execute(text("SELECT kind_id,payload FROM content_source_rows WHERE import_id=:id"), {"id": import_id}).all()
    if {key: row for key, row in saved} != release.smap:
        raise ValueError("stored source mismatch")
    payload = json.dumps(release.bmap, allow_nan=False, sort_keys=True)
    connection.execute(text(
        "INSERT INTO content_chapter_sources(import_id,payload) VALUES (:id,CAST(:payload AS jsonb)) "
        "ON CONFLICT (import_id) DO NOTHING"
    ), {"id": import_id, "payload": payload})
    stored = connection.execute(text("SELECT payload FROM content_chapter_sources WHERE import_id=:id"), {"id": import_id}).scalar_one_or_none()
    if stored != json.loads(payload):
        raise ValueError("chapter source mismatch")

def load_source_row(engine, import_id: UUID, kind_id: int) -> dict[str, Any]:
    from sqlalchemy import text

    with engine.connect() as connection:
        row = connection.execute(text("SELECT payload FROM content_source_rows WHERE import_id=:id AND kind_id=:kind"), {"id": import_id, "kind": kind_id}).scalar_one()
        return row

def publish_source(engine, import_id: UUID, server_id: int) -> dict[str, Any]:
    """Fail closed until gameplay validation and release activation exist."""
    raise ValueError("content validation is required before publish")

def prepare_draft(engine, import_id: UUID) -> dict[str, Any]:
    from sqlalchemy import text
    with engine.begin() as connection:
        source = connection.execute(text("SELECT source_sha256, status, row_count FROM content_source_imports WHERE id=:id FOR UPDATE"), {"id": import_id}).mappings().one_or_none()
        if source is None:
            raise ValueError("content import not found")
        rows = connection.execute(text("SELECT kind_id,payload FROM content_source_rows WHERE import_id=:id ORDER BY kind_id"), {"id": import_id}).mappings().all()
        if len(rows) != source["row_count"]:
            raise ValueError("content row count mismatch")
        chapters = connection.execute(text("SELECT payload FROM content_chapter_sources WHERE import_id=:id"), {"id": import_id}).scalar_one_or_none()
        if chapters is None:
            raise ValueError("chapter source missing; re-import verified source")
        graph = normal_map_graph({int(key): row for key, row in chapters.items()},
                                 {row["kind_id"]: row["payload"] for row in rows})
        document = {"format": "normal-map-draft-v1", "chapters": chapters,
                    "stages": [(row["kind_id"], row["payload"]) for row in rows]}
        rules_sha = hashlib.sha256(json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()
        version_id = uuid5(NAMESPACE_URL, f"kbht:draft:{source['source_sha256']}:{rules_sha}")
        inserted = connection.execute(text("INSERT INTO content_versions(id,source_sha256,rules_sha256,status) VALUES (:id,:source,:rules,'DRAFT') ON CONFLICT (id) DO NOTHING RETURNING id"), {"id": version_id, "source": source["source_sha256"], "rules": rules_sha}).scalar_one_or_none()
        stored = connection.execute(text("SELECT source_sha256,rules_sha256,status FROM content_versions WHERE id=:id FOR UPDATE"), {"id": version_id}).one()
        if tuple(stored) != (source["source_sha256"], rules_sha, "DRAFT"):
            raise ValueError("draft version mismatch")
        _materialize_graph(connection, version_id, graph, is_new=inserted is not None)
    return {"id": version_id, "status": "DRAFT", "source_import_id": import_id, "source_sha256": source["source_sha256"], "rules_sha256": rules_sha}


def _materialize_graph(connection, version_id: UUID, graph: dict, *, is_new: bool) -> None:
    from sqlalchemy import text

    maps = [{"content_version_id": version_id, "kind_id": key,
             **{field: value for field, value in row.items() if field != "waves"}}
            for key, row in graph.items()]
    waves = [{"content_version_id": version_id, "map_id": key, "zone": zone,
              "position": position, "mob_id": mob}
             for key, row in graph.items() for zone, wave in enumerate(row["waves"], 1)
             for position, mob in enumerate(wave, 1)]
    if is_new:
        for table, records in (("normal_map_definitions", maps), ("normal_map_waves", waves)):
            columns = list(records[0])
            connection.execute(text(f"INSERT INTO {table} ({','.join(columns)}) VALUES ({','.join(':' + col for col in columns)})"), records)
    for table, expected, order in (("normal_map_definitions", maps, "kind_id"),
                                    ("normal_map_waves", waves, "map_id,zone,position")):
        actual = connection.execute(text(f"SELECT * FROM {table} WHERE content_version_id=:id ORDER BY {order}"), {"id": version_id}).mappings().all()
        keys = order.split(",")
        expected = sorted(expected, key=lambda row: tuple(row[key] for key in keys))
        if [dict(row) for row in actual] != expected:
            raise ValueError("draft projection mismatch")

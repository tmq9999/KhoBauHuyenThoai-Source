import hashlib
import importlib.util
import io
import json
import os
import stat
import struct
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
ENTRY = ROOT / "tools" / "reference-index.py"

@pytest.fixture(scope="module")
def idx():
    assert ENTRY.is_file(), "write the implementation first"
    spec = importlib.util.spec_from_file_location("reference_index", ENTRY)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module

def zipped(entries):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, value, method in entries:
            zinfo = zipfile.ZipInfo()
            zinfo.filename = name
            z.writestr(zinfo, value, compress_type=method)
    return io.BytesIO(buf.getvalue())

def safe_zip(idx):
    fp = zipped([
        ("assets/project.manifest", '{"version":"1.0.0.02","assets":{}}', zipfile.ZIP_DEFLATED),
        ("assets/empty/", b"", zipfile.ZIP_STORED),
    ])
    idx.validate_zip(fp)
    assert not fp.closed

def test_entry_import_is_inert_and_errors_are_sanitized(idx, monkeypatch):
    seen = []
    monkeypatch.setattr(idx.zipfile, "ZipFile", lambda *a, **k: seen.append(a) or None)
    assert callable(idx.main)
    error = idx.IndexerError("ZIP_UNSAFE", "vn")
    assert str(error) == "ZIP_UNSAFE"
    assert error.artifact_id == "vn"
    assert seen == []

def test_safe_store_and_deflate_preserve_caller_cursor(idx):
    safe_zip(idx)

@pytest.mark.parametrize("name", ["/x", r"C:x", "../x", r"a\b", "a\x00b", "a//b", "./a", "a/../b"])
def test_unsafe_names_fail_without_payload_read(idx, name):
    with pytest.raises(idx.IndexerError) as error:
        idx.validate_zip(zipped([(name, b"x", zipfile.ZIP_STORED)]))
    assert error.value.code == "ZIP_UNSAFE"

def test_duplicate_casefold_alias_fails(idx):
    with pytest.raises(idx.IndexerError):
        idx.validate_zip(zipped([("assets/A", b"x", 0), ("assets/a", b"y", 0)]))

def test_corrupted_payload_reports_crc(idx):
    raw = bytearray(zipped([("a", b"payload", 0)]).getvalue())
    pos = raw.index(b"payload")
    raw[pos] ^= 1
    with pytest.raises(idx.IndexerError) as error:
        idx.validate_zip(io.BytesIO(raw))
    assert error.value.code == "ZIP_CRC_FAILED"

def test_limits_exact_and_plus_one(idx):
    exact = idx.Limits(entries=1, member_bytes=1, total_bytes=1, ratio=1000)
    idx.validate_zip(zipped([("a", b"x", 0)]), exact)
    with pytest.raises(idx.IndexerError):
        idx.validate_zip(zipped([("a", b"xy", 0)]), exact)
    with pytest.raises(idx.IndexerError):
        idx.validate_zip(zipped([("a", b"x", 0), ("b", b"", 0)]), idx.Limits(entries=1))

def test_encrypted_and_unsupported_method_flags_fail(idx):
    raw = bytearray(zipped([("a", b"x", 0)]).getvalue())
    raw[6] |= 1
    with pytest.raises(idx.IndexerError):
        idx.validate_zip(io.BytesIO(raw))
    raw = bytearray(zipped([("a", b"x", 0)]).getvalue())
    central = raw.rfind(b"PK\x01\x02")
    local = raw.find(b"PK\x03\x04")
    struct.pack_into("<H", raw, central + 10, 99)
    struct.pack_into("<H", raw, local + 8, 99)
    with pytest.raises(idx.IndexerError):
        idx.validate_zip(io.BytesIO(raw))

def test_no_extraction_and_no_network_or_subprocess_source(idx, tmp_path, monkeypatch):
    # Observe the validator's scratch area, not a live PostgreSQL cluster in work/.
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(idx, "__file__", str(tmp_path / "tools" / "reference-index.py"))
    before = {p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*") if p.is_file()}
    idx.validate_zip(zipped([("a", b"x", zipfile.ZIP_DEFLATED)]))
    after = {p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*") if p.is_file()}
    assert before == after
    source = ENTRY.read_text(encoding="utf-8")
    assert "import socket" not in source
    assert "import requests" not in source
    assert "import subprocess" not in source
    assert ".extractall" not in source

def test_synthetic_vn_scene_and_coverage(idx, tmp_path):
    manifest = {"version": "1.0.0.02", "assets": {
        "res/import/aa/scene-a.json": {},
        "res/import/aa/scene-b.json": {},
    }}
    paths = ["aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"]
    scene_a = {"__type__": "cc.SceneAsset", "_name": "home_scene"}
    scene_b = {"__type__": "cc.SceneAsset", "_name": "test"}
    entries = [
        ("assets/project.manifest", json.dumps(manifest), 0),
        ("assets/assetsx/paths.json", json.dumps(paths), 0),
        ("assets/assetsx/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/res/import/aa/scene-a.json", json.dumps(scene_a), 0),
        ("assets/assetsx/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/res/import/aa/scene-b.json", json.dumps(scene_b), 0),
    ]
    zf = zipfile.ZipFile(zipped(entries))
    scan = idx.inspect_metadata(zf, "vn", idx.Limits())
    assert scan.metadata["sceneCounts"] == {"allSerialized": 2, "product": 1}
    assert scan.metadata["manifestCoverage"]["missingPaths"] == 0
    assert scan.product_scene_keys == frozenset({"home_scene"})

def test_build_summary_uses_private_scene_sets(idx):
    def scan(artifact_id, names):
        return idx.ReferenceScan({"id": artifact_id, "fileName": idx.REGISTRY[artifact_id][0],
            "sha256": idx.REGISTRY[artifact_id][1], "sizeBytes": 1, "zipEntries": 1,
            "uncompressedBytes": 0, "assetFileCount": 0, "crcFirstBadEntry": None,
            "manifestVersion": "1.0.0.02", "manifestAssetCount": 0,
            "assetExtensionCounts": dict.fromkeys(idx.EXTENSIONS, 0),
            "sceneCounts": {"allSerialized": len(names), "product": len(names)},
            "manifestCoverage": {"missingPaths": 0, "ambiguousPaths": 0, "checksumStatus": "not-evaluated"}},
            frozenset(names))
    summary = idx.build_summary(scan("vn", {"a"}), scan("sp-comparator", {"a", "b"}))
    assert summary["comparison"]["sharedProductSceneCount"] == 1
    assert all("product_scene_keys" not in a for a in summary["referenceArtifacts"])

def test_encode_schema_and_canonical_newline(idx):
    summary = idx.expected_summary()
    payload = idx.encode_summary(summary)
    expected = (json.dumps(summary, ensure_ascii=True, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
    assert payload == expected
    assert idx.encode_summary(summary) == payload

@pytest.mark.parametrize("mutator", [
    lambda x: x["referenceArtifacts"][0].update({"unknown": True}),
    lambda x: x["referenceArtifacts"][0]["assetExtensionCounts"].update({"xml": 1}),
    lambda x: x["referenceArtifacts"][0].update({"sizeBytes": True}),
    lambda x: x["referenceArtifacts"][0].update({"sha256": "ABC"}),
    lambda x: x["referenceArtifacts"][0]["manifestCoverage"].update({"url": "https://x"}),
])
def test_encode_rejects_schema_leaks(idx, mutator):
    value = idx.expected_summary()
    mutator(value)
    with pytest.raises(idx.IndexerError) as error:
        idx.encode_summary(value)
    assert error.value.code == "OUTPUT_SCHEMA_INVALID"

def test_write_no_clobber(idx, tmp_path):
    root = tmp_path
    fixtures = root / "tools" / "fixtures"
    fixtures.mkdir(parents=True)
    payload = idx.encode_summary(idx.expected_summary())
    target = fixtures / "reference-summary.json"
    idx.write_summary(root, target, payload)
    assert target.read_bytes() == payload
    idx.write_summary(root, target, payload)
    target.write_bytes(b"old")
    with pytest.raises(idx.IndexerError) as error:
        idx.write_summary(root, target, payload)
    assert error.value.code == "OUTPUT_EXISTS"
    assert target.read_bytes() == b"old"

def test_main_hash_precedes_zip(tmp_path, idx, capsys, monkeypatch):
    monkeypatch.setattr(idx, "__file__", str(tmp_path / "tools" / "reference-index.py"))
    apk = tmp_path / "APK"
    apk.mkdir()
    (apk / "KhoBauHuyenThoai-VN.apk").write_bytes(b"wrong")
    (apk / "sp-071023.apk").write_bytes(b"wrong")
    rc = idx.main(["--root", str(tmp_path), "--output", str(tmp_path / "tools" / "fixtures" / "out.json")])
    assert rc == 3
    err = json.loads(capsys.readouterr().err)
    assert err["error"]["code"] == "REFERENCE_HASH_MISMATCH"

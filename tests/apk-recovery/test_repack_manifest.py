import hashlib
import json
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[2]
CLIENT = ROOT / "client-recovered"
LEDGER = CLIENT / "recovery-ledger.json"
BUILD = CLIENT / "scripts" / "build-repacked.ps1"


def test_recovery_ledger_pins_exact_native_repack_inputs():
    data = json.loads(LEDGER.read_text(encoding="utf-8"))

    assert data["status"] == "EDITABLE_CLIENT_BUILD_PARTIAL"
    assert data["original_apk"] == {
        "path": "APK/KhoBauHuyenThoai-VN.apk",
        "sha256": "d61d4ae1994ec5bcafdcfaf2406cc88ed9611cbb65da853027799d50d6687eb4",
    }
    assert data["native"] == {
        "path": "work/apk-vn/20260914T180000Z/apktool/lib/arm64-v8a/libcocos2djs.so",
        "sha256": "e348349e9c7ab476463092eee1f398eb360e37a74f9d96bf987ba43e164558d3",
    }
    assert data["apktool"] == {
        "path": "tools/decompiler/apktool_3.0.3.jar",
        "version": "3.0.3",
        "sha256": "dbf930b076c6b9be08d57c449cacefc3bdd6b71ebd59b3066fc0e1f5b14f9423",
    }
    assert data["sources"] == {
        "settings.js": "9c172efdc2c20f0543d25bce3a40c42b6aa6e8953bff873d1e8ec914ef482d47",
        "jsb_polyfill.js": "a5ba198936479dbbdaf14c03a88f9e70eb56a01509956b6ac963c93f886ac4a3",
        "project.js": "9776b6e20978d5d911bc0abb85830820bac5a3bfb8db4e65a617c5d18646a818",
    }


def test_validate_only_checks_real_inputs_without_creating_a_run():
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    if any(not (ROOT / ledger[key]["path"]).is_file() for key in ("original_apk", "native", "apktool")):
        pytest.skip("requires private local APK/native/Apktool inputs, not distributed through CI")
    before = {p.name for p in (ROOT / "work" / "apk-vn").iterdir()}
    result = subprocess.run(
        [
            "pwsh",
            "-NoProfile",
            "-File",
            str(BUILD),
            "-ValidateOnly",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    after = {p.name for p in (ROOT / "work" / "apk-vn").iterdir()}

    assert result.returncode == 0, result.stderr
    assert "VALIDATED" in result.stdout
    assert before == after


def test_client_sources_are_exact_safe_copies_of_recovery_outputs():
    recovered = ROOT / "work" / "apk-vn" / "20260914T140500Z-efc5da6a" / "recovered-js"
    mapping = {
        "settings.js": "settings.decoded",
        "jsb_polyfill.js": "jsb_polyfill.js",
        "project.js": "project.js",
    }
    if any(not (recovered / source).is_file() for source in mapping.values()):
        pytest.skip("requires original local decoder outputs; tracked source hashes are checked separately")
    for destination, source in mapping.items():
        assert (CLIENT / "src" / destination).read_bytes() == (recovered / source).read_bytes()


def test_tracked_client_payloads_still_match_pinned_recovery_hashes():
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    for name, digest in ledger["sources"].items():
        assert hashlib.sha256((CLIENT / "src" / name).read_bytes()).hexdigest() == digest

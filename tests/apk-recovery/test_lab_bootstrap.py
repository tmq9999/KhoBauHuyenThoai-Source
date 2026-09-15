import copy
import hashlib
import importlib.util
import json
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace
import io

import pytest


ROOT = Path(__file__).parents[2]
HELPER_PATH = ROOT / "tools" / "apk-recovery" / "prepare-lab-bootstrap.py"
PROJECT_SOURCE = ROOT / "client-recovered" / "src" / "project.js"
APK_MANIFEST = ROOT / "work" / "apk-vn" / "20260914T180000Z" / "apktool" / "assets" / "project.manifest"


def _helper_module():
    spec = importlib.util.spec_from_file_location("prepare_lab_bootstrap", HELPER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_remap_changes_only_the_single_observed_build_ext_assignment_block():
    helper = _helper_module()
    original = PROJECT_SOURCE.read_text(encoding="utf-8")
    original_hash = hashlib.sha256(PROJECT_SOURCE.read_bytes()).hexdigest()

    transformed = helper.remap_build_ext_text(original)

    assert hashlib.sha256(PROJECT_SOURCE.read_bytes()).hexdigest() == original_hash
    assert transformed.count('a.url = "http://127.0.0.1:20003";') == 1
    assert transformed.count('a.staticUrl = "http://127.0.0.1:20001";') == 1
    assert transformed.count('a.gateHost = "127.0.0.1";') == 1
    assert transformed.count('a.gatePort = "20100";') == 1
    assert helper.BUILD_EXT_ASSIGNMENTS.sub(lambda match: match.group(0), original) == original
    assert helper.BUILD_EXT_ASSIGNMENTS.sub(lambda match: match.group(0), transformed).replace(
        helper.LAB_ASSIGNMENTS, helper.ORIGINAL_ASSIGNMENTS
    ) == original


def test_default_build_does_not_select_the_lab_transform():
    build = (ROOT / "client-recovered" / "scripts" / "build-repacked.ps1").read_text(encoding="utf-8")

    assert "[switch]$LabBootstrap" in build
    assert "if ($LabBootstrap)" in build
    assert "$sourceForBuild = $sourceRoot" in build


def test_local_auth_transform_patches_exact_sdk_init_and_preserves_other_text():
    helper = _helper_module()
    original = PROJECT_SOURCE.read_text(encoding="utf-8")
    remapped = helper.remap_build_ext_text(original)
    transformed = helper.apply_local_auth_transform(remapped)
    assert transformed.count('d.sdkName = "mmx";') == 3
    assert 'd.channel = "Android";' in transformed
    assert 'jsb.reflection.callStaticMethod("org/cocos2dx/javascript/SDKAdapter", "initPackageInfo", "()V")' not in transformed
    expected = remapped.replace(helper.SDK_INIT_ANDROID_CALL, helper.SDK_INIT_ANDROID_LOCAL_CALL, 1)
    for original_log, replacement in helper.LOCAL_AUTH_LOG_CALLS:
        expected = expected.replace(original_log, replacement, 1)
    expected = expected.replace(helper.RPC_CALLBACK_CATCH, helper.RPC_CALLBACK_DIAGNOSTIC, 1)
    assert transformed == expected


def test_local_auth_transform_rejects_missing_or_multiple_pinned_init_blocks():
    helper = _helper_module()
    original = PROJECT_SOURCE.read_text(encoding="utf-8")
    remapped = helper.remap_build_ext_text(original)
    with pytest.raises(ValueError, match="exactly one"):
        helper.apply_local_auth_transform(remapped.replace(helper.SDK_INIT_ANDROID_CALL, "", 1))
    with pytest.raises(ValueError, match="exactly one"):
        helper.apply_local_auth_transform(remapped + helper.SDK_INIT_ANDROID_CALL)


def test_local_auth_patch_rejects_changed_staged_source_and_reference_alias(tmp_path):
    helper = _helper_module()
    original = PROJECT_SOURCE.read_bytes()
    reference = tmp_path / "reference.js"
    staged = tmp_path / "staged.js"
    reference.write_bytes(original)
    staged.write_bytes(original)
    with pytest.raises(ValueError, match="same path"):
        helper.patch_local_auth_staged_source(reference, reference)
    staged.write_bytes(helper.remap_build_ext_text(original.decode("utf-8")).encode("utf-8") + b"// changed")
    with pytest.raises(ValueError, match="staged source"):
        helper.patch_local_auth_staged_source(staged, reference)


def test_local_auth_switch_requires_lab_bootstrap_and_is_opt_in():
    build = (ROOT / "client-recovered" / "scripts" / "build-repacked.ps1").read_text(encoding="utf-8")
    assert "[switch]$LabLocalAuth" in build
    assert "if ($LabLocalAuth -and -not $LabBootstrap)" in build
    assert "patch-local-auth" in build


def test_local_auth_transform_removes_only_two_pinned_http_console_payload_logs():
    helper = _helper_module()
    original = PROJECT_SOURCE.read_text(encoding="utf-8")
    remapped = helper.remap_build_ext_text(original)
    transformed = helper.apply_local_auth_transform(remapped)
    assert transformed.count('console.log(t);') == 0
    assert transformed.count('console.log(e + " " + JSON.stringify(t));') == 0
    assert transformed.replace(helper.LOCAL_AUTH_LOG_CALLS[0][0], helper.LOCAL_AUTH_LOG_CALLS[0][1], 1) != remapped
    assert 'console.log("isWin:" + d);' in transformed


def test_local_auth_transform_rejects_missing_or_duplicate_http_log_pins():
    helper = _helper_module()
    remapped = helper.remap_build_ext_text(PROJECT_SOURCE.read_text(encoding="utf-8"))
    missing = remapped.replace(helper.LOCAL_AUTH_LOG_CALLS[0][0], "", 1)
    with pytest.raises(ValueError, match="HTTP log pin"):
        helper.apply_local_auth_transform(missing)
    duplicate = remapped + helper.LOCAL_AUTH_LOG_CALLS[1][0]
    with pytest.raises(ValueError, match="HTTP log pin"):
        helper.apply_local_auth_transform(duplicate)


def test_remap_refuses_a_staged_source_that_no_longer_matches_the_pinned_original(tmp_path):
    helper = _helper_module()
    reference = tmp_path / "project.reference.js"
    staged = tmp_path / "project.staged.js"
    reference.write_text('i.init = function() {\n' + helper.ORIGINAL_ASSIGNMENTS + '\n}\n', encoding="utf-8")
    staged.write_text(reference.read_text(encoding="utf-8") + "// changed\n", encoding="utf-8")

    with pytest.raises(ValueError, match="pinned original"):
        helper.remap_staged_source(staged, reference)

    assert staged.read_text(encoding="utf-8").endswith("// changed\n")


def test_remap_refuses_a_mutated_reference_even_when_stage_matches_it(tmp_path):
    helper = _helper_module()
    reference = tmp_path / "project.reference.js"
    staged = tmp_path / "project.staged.js"
    mutated = 'i.init = function() {\n' + helper.ORIGINAL_ASSIGNMENTS.replace("20100", "20101") + '\n}\n'
    reference.write_text(mutated, encoding="utf-8")
    staged.write_text(mutated, encoding="utf-8")

    with pytest.raises(ValueError, match="pinned original"):
        helper.remap_staged_source(staged, reference)


def test_remap_refuses_to_overwrite_the_reference_source(tmp_path):
    helper = _helper_module()
    source = tmp_path / "project.js"
    source.write_text('i.init = function() {\n' + helper.ORIGINAL_ASSIGNMENTS + '\n}\n', encoding="utf-8")

    with pytest.raises(ValueError, match="same path"):
        helper.remap_staged_source(source, source)


def test_remap_refuses_a_hardlinked_stage_before_it_can_overwrite_the_reference(tmp_path, monkeypatch):
    helper = _helper_module()
    reference = tmp_path / "project.reference.js"
    staged = tmp_path / "project.staged.js"
    source = 'i.init = function() {\n' + helper.ORIGINAL_ASSIGNMENTS + '\n}\n'
    reference.write_text(source, encoding="utf-8")
    os.link(reference, staged)
    monkeypatch.setattr(helper, "PINNED_PROJECT_SHA256", hashlib.sha256(reference.read_bytes()).hexdigest())
    before = reference.read_bytes()

    with pytest.raises(ValueError, match="same file"):
        helper.remap_staged_source(staged, reference)

    assert reference.read_bytes() == before


def test_manifest_rewrite_bounds_bytes_actually_read_not_only_stat_size(tmp_path):
    helper = _helper_module()
    raw = json.dumps({"assets": {}, "padding": "x" * (2 * 1024 * 1024)}).encode("utf-8")

    class LyingManifest:
        def is_symlink(self):
            return False

        def is_file(self):
            return True

        def stat(self):
            return SimpleNamespace(st_size=1)

        def open(self, mode):
            assert mode == "rb"
            return io.BytesIO(raw)

    with pytest.raises(ValueError, match="2 MiB"):
        helper._manifest_payload(LyingManifest())


def test_manifest_keeps_resources_and_hashes_actual_staged_jsc_bytes(tmp_path):
    helper = _helper_module()
    manifest_path = tmp_path / "project.manifest"
    lab_manifest = tmp_path / "lab" / "project.manifest"
    manifest_path.write_bytes(APK_MANIFEST.read_bytes())
    encoded = tmp_path / "encoded"
    encoded.mkdir()
    payloads = {
        "settings.jsc": b"settings staged bytes",
        "jsb_polyfill.jsc": b"polyfill staged bytes",
        "project.jsc": b"project staged bytes",
    }
    for name, body in payloads.items():
        (encoded / name).write_bytes(body)
    before = json.loads(manifest_path.read_text(encoding="utf-8"))

    digest = helper.rewrite_manifest(manifest_path, encoded, lab_manifest)
    after = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert after["version"] == before["version"] == "1.0.0.02"
    assert after["assets"].keys() == before["assets"].keys()
    assert after["remoteVersionUrl"] == "http://127.0.0.1:20001/update/version.manifest"
    assert after["remoteManifestUrl"] == "http://127.0.0.1:20001/update/project.manifest"
    assert after["packageUrl"] == "http://127.0.0.1:20001/update/1.0.0.02"
    assert after["host"] == "127.0.0.1:20001"
    for name, body in payloads.items():
        assert after["assets"][f"src/{name}"]["md5"] == hashlib.md5(body).hexdigest()
    assert lab_manifest.read_bytes() == manifest_path.read_bytes()
    assert digest == hashlib.sha256(lab_manifest.read_bytes()).hexdigest()


def test_manifest_rewrite_refuses_missing_encoded_payload(tmp_path):
    helper = _helper_module()
    manifest_path = tmp_path / "project.manifest"
    manifest_path.write_bytes(APK_MANIFEST.read_bytes())
    encoded = tmp_path / "encoded"
    encoded.mkdir()

    with pytest.raises(ValueError, match="missing encoded payload"):
        helper.rewrite_manifest(manifest_path, encoded, tmp_path / "lab.manifest")


def test_local_auth_diagnostic_transform_is_exact_pinned_and_node_syntax_valid(tmp_path):
    helper = _helper_module()
    original = PROJECT_SOURCE.read_text(encoding="utf-8")
    remapped = helper.remap_build_ext_text(original)
    transformed = helper.apply_local_auth_transform(remapped)
    assert transformed.count("LAB_RPC_CALLBACK_ERROR") == 1
    assert "e.message" not in helper.RPC_CALLBACK_DIAGNOSTIC
    assert "JSON.stringify(e)" not in helper.RPC_CALLBACK_DIAGNOSTIC
    assert r"project\.js:\d+:\d+" in helper.RPC_CALLBACK_DIAGNOSTIC
    assert "String(e && e.name)" not in helper.RPC_CALLBACK_DIAGNOSTIC
    assert "labNames" in helper.RPC_CALLBACK_DIAGNOSTIC
    output = tmp_path / "project.js"
    output.write_text(transformed, encoding="utf-8")
    checked = subprocess.run(["node", "--check", str(output)], capture_output=True, text=True)
    assert checked.returncode == 0, checked.stderr


def test_local_auth_diagnostic_transform_fails_closed_on_missing_or_duplicate_catch_pin():
    helper = _helper_module()
    original = PROJECT_SOURCE.read_text(encoding="utf-8")
    remapped = helper.remap_build_ext_text(original)
    assert remapped.count(helper.RPC_CALLBACK_CATCH) == 1
    with pytest.raises(ValueError, match="callback catch pin"):
        helper.apply_local_auth_transform(remapped.replace(helper.RPC_CALLBACK_CATCH, "", 1))
    with pytest.raises(ValueError, match="callback catch pin"):
        helper.apply_local_auth_transform(remapped + helper.RPC_CALLBACK_CATCH)


def test_local_auth_diagnostic_object_name_is_coerced_to_fixed_error_label(tmp_path):
    helper = _helper_module()
    block = helper.RPC_CALLBACK_DIAGNOSTIC
    body = block[len("} catch (e) {"): -len("\n}")]
    script = """
var logs = [];
console.log = function () { logs.push(Array.prototype.slice.call(arguments)); };
var cc = {sys: {isNative: true}};
var e = {name: {toString: function () { return 'TypeError'; }}, stack: 'Error at project.js:12:34'};
try { throw e; } catch (e) { BODY }
process.stdout.write(JSON.stringify(logs));
""".replace("BODY", body)
    output = tmp_path / "diagnostic.js"
    output.write_text(script, encoding="utf-8")
    checked = subprocess.run(["node", str(output)], capture_output=True, text=True)
    assert checked.returncode == 0, checked.stderr
    logs = json.loads(checked.stdout)
    assert logs == [["LAB_RPC_CALLBACK_ERROR", "Error", "project.js:12:34"]]


def test_local_auth_diagnostic_survives_throwing_error_property_getters(tmp_path):
    helper = _helper_module()
    block = helper.RPC_CALLBACK_DIAGNOSTIC
    body = block[len("} catch (e) {"): -len("\n}")]
    script = """
var logs = [];
console.log = function () { logs.push(Array.prototype.slice.call(arguments)); };
var cc = {sys: {isNative: true}};
var e = {};
Object.defineProperty(e, 'name', {get: function () { throw new Error('do not leak name'); }});
Object.defineProperty(e, 'stack', {get: function () { throw new Error('do not leak stack'); }});
try { throw e; } catch (e) { BODY }
process.stdout.write(JSON.stringify(logs));
""".replace("BODY", body)
    output = tmp_path / "diagnostic-hostile-getter.js"
    output.write_text(script, encoding="utf-8")
    checked = subprocess.run(["node", str(output)], capture_output=True, text=True)
    assert checked.returncode == 0, checked.stderr
    assert json.loads(checked.stdout) == [["LAB_RPC_CALLBACK_ERROR", "Error", ""]]

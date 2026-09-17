from __future__ import annotations

import hashlib
import importlib.util
import os
import re
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "client-recovered/src/project.js"
BRIDGE = ROOT / "client-recovered/patches/inventory-bridge.js"
INTEGRATION = ROOT / "client-recovered/patches/inventory-integration.js"
STAGER = ROOT / "tools/apk-recovery/stage-client-patches.py"
PREPARE = ROOT / "tools/apk-recovery/prepare-lab-bootstrap.py"


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


@pytest.mark.parametrize("power_display", [False, True])
def test_integration_transform_preserves_reference_and_hooks_exact_socket_pin(tmp_path, power_display):
    prepare = module(PREPARE, "prepare")
    stager = module(STAGER, "stager")
    original = SOURCE.read_bytes()
    stage = tmp_path / "project.js"
    predecessor = prepare.apply_local_auth_transform(prepare.remap_build_ext_text(original.decode()))
    if power_display:
        predecessor = prepare.apply_power_display_transform(predecessor)
    stage.write_bytes(predecessor.encode("utf-8"))
    digest = stager.integrate_inventory_bridge(stage, SOURCE, BRIDGE, INTEGRATION,
                                              stage_root=tmp_path, power_display=power_display)
    result = stage.read_text(encoding="utf-8")
    assert result.count(stager.SOCKET_REQUEST_HOOK) == 1
    assert result.startswith(BRIDGE.read_text(encoding="utf-8"))
    assert "root.kbhtInventoryIntegration =" in result
    assert hashlib.sha256(stage.read_bytes()).hexdigest() == digest
    assert SOURCE.read_bytes() == original
    checked = subprocess.run(["node", "--check", str(stage)], capture_output=True, timeout=30)
    assert checked.returncode == 0, checked.stderr.decode()


def test_stager_rejects_wrong_prior_transform_existing_target_and_bad_reference(tmp_path):
    stager = module(STAGER, "stager_bad")
    stage = tmp_path / "project.js"
    stage.write_text("u.request = function(e, t, n) {}", encoding="utf-8")
    with pytest.raises(ValueError, match="prior transforms"):
        stager.integrate_inventory_bridge(stage, SOURCE, BRIDGE, INTEGRATION, stage_root=tmp_path)
    bad = tmp_path / "bad.js"
    bad.write_text("bad", encoding="utf-8")
    clean = tmp_path / "stage"
    (clean / "assets/src").mkdir(parents=True)
    (clean / "assets/src/inventory-bridge.js").write_text("existing", encoding="utf-8")
    with pytest.raises(ValueError, match="already exists"):
        stager.stage_inventory_bridge(clean, BRIDGE, SOURCE)
    with pytest.raises(ValueError, match="pinned"):
        stager.stage_inventory_bridge(tmp_path, BRIDGE, bad)


def test_stager_rejects_symlinked_input_and_destination_parent(tmp_path):
    stager = module(STAGER, "stager_links")
    linked_patch = tmp_path / "bridge-link.js"
    try:
        linked_patch.symlink_to(BRIDGE)
    except OSError as error:
        if os.name == "nt" and getattr(error, "winerror", None) == 1314:
            pytest.skip("Windows symlink privilege unavailable")
        raise
    stage = tmp_path / "stage"
    (stage / "assets/src").mkdir(parents=True)
    with pytest.raises(ValueError, match="linked"):
        stager.stage_inventory_bridge(stage, linked_patch, SOURCE)
    escaped = tmp_path / "escaped"
    escaped.mkdir()
    shutil_target = stage / "assets/src"
    shutil_target.rmdir()
    shutil_target.symlink_to(escaped, target_is_directory=True)
    with pytest.raises(ValueError, match="linked"):
        stager.stage_inventory_bridge(stage, BRIDGE, SOURCE)


def test_stager_rejects_hardlink_alias_inputs(tmp_path):
    stager = module(STAGER, "stager_hardlink")
    reference = tmp_path / "reference.js"
    patch_alias = tmp_path / "patch.js"
    reference.write_bytes(SOURCE.read_bytes())
    try:
        os.link(reference, patch_alias)
    except OSError:
        pytest.skip("hardlink unavailable")
    stage = tmp_path / "stage"
    stage.mkdir()
    with pytest.raises(ValueError, match="alias"):
        stager.stage_inventory_bridge(stage, patch_alias, reference)


def test_integration_rejects_pairwise_hardlink_aliases(tmp_path):
    prepare = module(PREPARE, "prepare_aliases")
    stager = module(STAGER, "stager_aliases")
    reference = tmp_path / "reference.js"
    reference.write_bytes(SOURCE.read_bytes())
    stage = tmp_path / "project.js"
    stage.write_bytes(prepare.apply_local_auth_transform(prepare.remap_build_ext_text(reference.read_bytes().decode("utf-8"))).encode())
    alias = tmp_path / "alias.js"
    bridge_copy = tmp_path / "bridge.js"
    bridge_copy.write_bytes(BRIDGE.read_bytes())
    os.link(bridge_copy, alias)
    with pytest.raises(ValueError, match="alias"):
        stager.integrate_inventory_bridge(stage, reference, bridge_copy, alias, stage_root=tmp_path)


def test_builder_requires_explicit_lab_bootstrap_and_local_auth():
    result = subprocess.run(
        ["pwsh", "-NoProfile", "-File", str(ROOT / "client-recovered/scripts/build-repacked.ps1"),
         "-InventoryBridge", "-ValidateOnly"],
        cwd=ROOT, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode != 0
    assert "requires" in result.stderr
    assert "-LabBootstrap" in result.stderr
    assert "-LabLocalAuth" in result.stderr


def prepared_project(path):
    prepare = module(PREPARE, "prepare_boundary")
    path.write_bytes(prepare.apply_local_auth_transform(
        prepare.remap_build_ext_text(SOURCE.read_bytes().decode())).encode())
    return path.read_bytes()


def test_integration_requires_explicit_stage_root_before_mutation(tmp_path):
    stager = module(STAGER, "stager_root_required")
    stage = tmp_path / "project.js"
    before = prepared_project(stage)
    with pytest.raises((TypeError, ValueError), match="stage_root|stage root"):
        stager.integrate_inventory_bridge(stage, SOURCE, BRIDGE, INTEGRATION)
    assert stage.read_bytes() == before


def test_integration_rejects_destination_outside_explicit_stage_root(tmp_path):
    stager = module(STAGER, "stager_outside")
    root = tmp_path / "stage"
    root.mkdir()
    outside = tmp_path / "project.js"
    before = prepared_project(outside)
    with pytest.raises(ValueError, match="outside|escape"):
        stager.integrate_inventory_bridge(outside, SOURCE, BRIDGE, INTEGRATION, stage_root=root)
    assert outside.read_bytes() == before


def test_integration_rejects_staged_hardlink_to_unlisted_outside_file(tmp_path):
    stager = module(STAGER, "stager_external_hardlink")
    root = tmp_path / "stage"
    root.mkdir()
    outside = tmp_path / "outside.js"
    before = prepared_project(outside)
    destination = root / "project.js"
    os.link(outside, destination)
    with pytest.raises(ValueError, match="hardlink|alias"):
        stager.integrate_inventory_bridge(destination, SOURCE, BRIDGE, INTEGRATION, stage_root=root)
    assert outside.read_bytes() == before
    assert destination.read_bytes() == before


@pytest.mark.parametrize("link_kind", ["root", "ancestor", "destination", "parent"])
def test_integration_rejects_linked_stage_paths(tmp_path, link_kind):
    stager = module(STAGER, "stager_link_boundaries")
    root = tmp_path / "stage"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    project = outside / "project.js"
    before = prepared_project(project)
    link = root / "link"
    try:
        link.symlink_to(project if link_kind == "destination" else outside,
                        target_is_directory=link_kind != "destination")
    except OSError as error:
        if os.name == "nt" and getattr(error, "winerror", None) == 1314:
            pytest.skip("Windows symlink privilege unavailable")
        raise
    destination = link if link_kind == "destination" else link / "project.js"
    selected_root = link if link_kind == "root" else root
    if link_kind == "ancestor":
        (outside / "child").mkdir()
        selected_root = link / "child"
        destination = selected_root / "project.js"
        prepared_project(outside / "child/project.js")
    with pytest.raises(ValueError, match="linked"):
        stager.integrate_inventory_bridge(destination, SOURCE, BRIDGE, INTEGRATION, stage_root=selected_root)
    assert project.read_bytes() == before


def test_integration_cli_requires_stage_root_without_mutation(tmp_path):
    stage = tmp_path / "project.js"
    before = prepared_project(stage)
    result = subprocess.run(["python", str(STAGER), "integrate-inventory-bridge",
        "--input", str(stage), "--reference-project", str(SOURCE), "--bridge", str(BRIDGE),
        "--integration", str(INTEGRATION)], capture_output=True, text=True, timeout=30)
    assert result.returncode != 0
    assert "--stage-root" in result.stderr
    assert stage.read_bytes() == before


@pytest.mark.skipif(os.name != "nt", reason="Windows junction boundary")
def test_integration_rejects_junction_escape_without_symlink_privilege(tmp_path):
    stager = module(STAGER, "stager_junction")
    root = tmp_path / "stage"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    project = outside / "project.js"
    before = prepared_project(project)
    link = root / "linked"
    result = subprocess.run(["pwsh", "-NoProfile", "-Command",
        f"New-Item -ItemType Junction -Path '{link}' -Target '{outside}' | Out-Null"],
        capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    with pytest.raises(ValueError, match="linked"):
        stager.integrate_inventory_bridge(link / "project.js", SOURCE, BRIDGE, INTEGRATION, stage_root=root)
    assert project.read_bytes() == before


def test_builder_inventory_command_passes_validated_source_stage(tmp_path):
    # Execute the builder's real stager command only, not an APK build.
    builder = (ROOT / "client-recovered/scripts/build-repacked.ps1").read_text(encoding="utf-8")
    command = re.search(r"^\s*(& python \$patchStager integrate-inventory-bridge[^\n]+)", builder, re.MULTILINE).group(1)
    source_stage = tmp_path / "stage"
    source_stage.mkdir()
    project = source_stage / "project.js"
    prepared_project(project)
    script = (f"$patchStager = '{STAGER}'; $sourceStage = '{source_stage}'; "
              f"$sourceRoot = '{SOURCE.parent}'; $clientRoot = '{BRIDGE.parent.parent}'; "
              "$powerArg = @(); " + command + "; exit $LASTEXITCODE")
    result = subprocess.run(["pwsh", "-NoProfile", "-Command", script],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert project.read_bytes().startswith(BRIDGE.read_bytes())

import hashlib
import importlib.util
import json
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
HELPER = ROOT / "tools/apk-recovery/prepare-lab-bootstrap.py"
SOURCE = ROOT / "client-recovered/src/project.js"


@pytest.fixture
def helper():
    spec = importlib.util.spec_from_file_location("lab_power_patch", HELPER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_patch_transforms_real_ui_expressions_but_not_source_or_numeric_stats(helper, tmp_path):
    assert hasattr(helper, "patch_power_display_staged_source"), "M0.2 staged power patch is missing"
    original = SOURCE.read_bytes()
    staged = tmp_path / "project.js"
    staged.write_bytes(original)
    helper.remap_staged_source(staged, SOURCE)
    helper.patch_local_auth_staged_source(staged, SOURCE)
    before = staged.read_text(encoding="utf-8")
    digest = helper.patch_power_display_staged_source(staged, SOURCE)
    after = staged.read_text(encoding="utf-8")
    assert SOURCE.read_bytes() == original
    assert digest == hashlib.sha256(staged.read_bytes()).hexdigest()
    assert 'this.powerLabel.string = window.kbhtPowerDisplay.formatPower(n.power);' in after
    assert 'this.powerLabel.string = window.kbhtPowerDisplay.formatPower(t.totalPower);' in after
    assert 'window.kbhtPowerDisplay.formatRankValue(e.myValue, e.typeInfo.type)' in after
    assert 'window.kbhtPowerDisplay.formatRankValue(r.value, e.typeInfo.type)' in after
    assert after.count('getPower: function(e, t)') == before.count('getPower: function(e, t)') == 1
    # Parse the complete staged bundle; never execute recovered client code.
    result = subprocess.run(["node", "--check", str(staged)], capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr.decode()


def test_patch_rejects_reference_alias_and_changed_stage_without_writing(helper, tmp_path):
    assert hasattr(helper, "patch_power_display_staged_source"), "M0.2 staged power patch is missing"
    with pytest.raises(ValueError, match="same"):
        helper.patch_power_display_staged_source(SOURCE, SOURCE)
    staged = tmp_path / "project.js"
    staged.write_bytes(SOURCE.read_bytes())
    with pytest.raises(ValueError, match="expected local-auth"):
        helper.patch_power_display_staged_source(staged, SOURCE)
    assert staged.read_bytes() == SOURCE.read_bytes()


def test_patch_rejects_missing_or_duplicate_exact_pins(helper):
    assert hasattr(helper, "apply_power_display_transform"), "M0.2 display transform is missing"
    source = SOURCE.read_text(encoding="utf-8")
    for value in (source.replace('this.powerLabel.string = n.power;', '', 1),
                  source + '\nthis.powerLabel.string = n.power;'):
        with pytest.raises(ValueError, match="power display pin"):
            helper.apply_power_display_transform(value)


def test_transformed_home_roster_team_and_rank_assignments_render_integer_power(helper):
    assert hasattr(helper, "apply_power_display_transform")
    after = helper.apply_power_display_transform(SOURCE.read_text(encoding="utf-8"))
    # Execute only the authored formatter and individual display assignments;
    # no recovered module, loader, network or native glue is executed.
    expressions = []
    for prefix in ("this.powerLabel.string = window.kbhtPowerDisplay.formatPower(n.power);",
                   "this.powerLabel.string = window.kbhtPowerDisplay.formatPower(t.totalPower);"):
        assert prefix in after
        expressions.append(prefix)
    script = "\n".join([
        "const assert = require('node:assert/strict');",
        "var window = {kbhtPowerDisplay: require(" + json.dumps(str(ROOT / 'client-recovered/patches/power-display.js')) + ")};",
        "const n = {power:3873.0999999999999}, t = {totalPower:980.2+980.2+978.2};",
        "const panel = {powerLabel:{string:''}};",
        "(function(){" + expressions[0] + "}).call(panel);",
        "assert.equal(panel.powerLabel.string, '3873');",
        "(function(){" + expressions[1] + "}).call(panel);",
        "assert.equal(panel.powerLabel.string, '2938');",
        "assert.equal(n.power,3873.0999999999999);",
        "assert.equal(window.kbhtPowerDisplay.formatRankValue(n.power,'totalPower'),'3873');",
        "assert.equal(window.kbhtPowerDisplay.formatRankValue(12,'level'),12);",
    ])
    result = subprocess.run(["node", "-e", script], capture_output=True, timeout=10)
    assert result.returncode == 0, result.stderr.decode()


def test_power_patch_refuses_hardlink_to_pinned_reference(helper, tmp_path):
    reference = tmp_path / "reference.js"
    reference.write_bytes(SOURCE.read_bytes())
    stage = tmp_path / "stage.js"
    stage.hardlink_to(reference)
    with pytest.raises(ValueError, match="same file"):
        helper.patch_power_display_staged_source(stage, reference)
    assert reference.read_bytes() == SOURCE.read_bytes()


def test_power_build_requires_opt_in_lab_auth_before_creating_run(tmp_path):
    result = subprocess.run(["pwsh", "-NoProfile", "-File", str(ROOT / "client-recovered/scripts/build-repacked.ps1"),
                             "-PowerDisplay", "-ValidateOnly"], cwd=ROOT, capture_output=True, timeout=30)
    assert result.returncode != 0
    assert b"requires -LabBootstrap -LabLocalAuth" in result.stderr

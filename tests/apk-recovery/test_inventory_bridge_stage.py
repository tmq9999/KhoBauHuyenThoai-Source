from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "client-recovered/src/project.js"
PATCH = ROOT / "client-recovered/patches/inventory-bridge.js"
HELPER = ROOT / "tools/apk-recovery/stage-client-patches.py"
PINNED_PROJECT_SHA = "9776b6e20978d5d911bc0abb85830820bac5a3bfb8db4e65a617c5d18646a818"


def test_inventory_bridge_stages_as_inert_asset_without_touching_pinned_project(tmp_path):
    stage = tmp_path / "apktool-stage"
    (stage / "assets/src").mkdir(parents=True)
    original_project = PROJECT.read_bytes()
    result = subprocess.run(
        [
            "python", "-I", str(HELPER), "stage-inventory-bridge",
            "--stage-root", str(stage), "--patch", str(PATCH),
            "--reference-project", str(PROJECT),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
    staged = stage / "assets/src/inventory-bridge.js"
    assert staged.read_bytes() == PATCH.read_bytes()
    assert hashlib.sha256(staged.read_bytes()).hexdigest() == hashlib.sha256(PATCH.read_bytes()).hexdigest()
    assert PROJECT.read_bytes() == original_project
    assert hashlib.sha256(original_project).hexdigest() == PINNED_PROJECT_SHA


def test_inventory_bridge_builder_flag_is_opt_in_and_reports_staged_hash():
    builder = (ROOT / "client-recovered/scripts/build-repacked.ps1").read_text(encoding="utf-8")
    assert "[switch]$InventoryBridge" in builder
    assert "stage-client-patches.py" in builder
    assert "integrate-inventory-bridge" in builder
    assert "Inventory bridge staging: enabled" in builder
    assert "if ($InventoryBridge)" in builder

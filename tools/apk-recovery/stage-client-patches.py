"""Stage reviewed standalone client patches without modifying recovered source."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import os
import stat
from pathlib import Path


PINNED_PROJECT_SHA256 = "9776b6e20978d5d911bc0abb85830820bac5a3bfb8db4e65a617c5d18646a818"
SOCKET_REQUEST_PIN = "u.request = function(e, t, n) {"
SOCKET_REQUEST_HOOK = 'if (window.kbhtInventoryIntegration && window.kbhtInventoryIntegration.handleRequest(e, t, n)) return;'


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _is_linklike(path: Path) -> bool:
    if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
        return True
    try:
        attributes = getattr(path.lstat(), "st_file_attributes", 0)
    except FileNotFoundError:
        return False
    return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


def _require_plain_file(path: Path, label: str) -> Path:
    current = path
    while current != current.parent:
        if _is_linklike(current):
            raise ValueError(f"{label} is linked")
        current = current.parent
    if not path.is_file():
        raise ValueError(f"{label} is missing or linked")
    return path.resolve(strict=True)


def _validate_stage(stage_root: Path) -> Path:
    if _is_linklike(stage_root) or not stage_root.is_dir():
        raise ValueError("stage root is missing or linked")
    current = stage_root
    while current != current.parent:
        if _is_linklike(current):
            raise ValueError("stage root ancestor is linked")
        current = current.parent
    return stage_root.resolve(strict=True)


def _under(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def stage_inventory_bridge(stage_root: Path, patch: Path, reference_project: Path) -> str:
    stage_root = _validate_stage(stage_root)
    patch = _require_plain_file(patch, "inventory bridge patch")
    reference_project = _require_plain_file(reference_project, "reference project")
    if os.path.samefile(patch, reference_project):
        raise ValueError("patch and reference project must not alias")
    if _sha256(reference_project) != PINNED_PROJECT_SHA256:
        raise ValueError("reference project does not match pinned source")
    target = stage_root / "assets" / "src" / "inventory-bridge.js"
    for parent in (stage_root / "assets", stage_root / "assets" / "src"):
        if parent.exists() and (_is_linklike(parent) or not parent.is_dir()):
            raise ValueError("staging destination parent is linked or invalid")
        parent.mkdir(exist_ok=True)
    resolved_parent = target.parent.resolve(strict=True)
    if not _under(resolved_parent, stage_root):
        raise ValueError("staging destination escapes stage root")
    if target.exists() or _is_linklike(target):
        raise ValueError("staging target already exists")
    if target.resolve(strict=False) in (patch, reference_project):
        raise ValueError("staging target must not be the patch source")
    target.write_bytes(patch.read_bytes())
    return _sha256(target)


def integrate_inventory_bridge(staged_project: Path, reference_project: Path, bridge: Path,
                               integration: Path, *, stage_root: Path, power_display: bool = False) -> str:
    root = _validate_stage(stage_root)
    staged = _require_plain_file(staged_project, "staged project")
    if not _under(staged, root):
        raise ValueError("staged project escapes stage root")
    # Pairwise input checks cannot detect aliases to unlisted files outside the
    # stage. Never modify a multiply-linked inode, even if its path is inside.
    if staged.stat().st_nlink != 1:
        raise ValueError("staged project has a hardlink alias")
    reference = _require_plain_file(reference_project, "reference project")
    bridge_path = _require_plain_file(bridge, "inventory bridge")
    integration_path = _require_plain_file(integration, "inventory integration")
    inputs = (staged, reference, bridge_path, integration_path)
    for left in range(len(inputs)):
        for right in range(left + 1, len(inputs)):
            if os.path.samefile(inputs[left], inputs[right]):
                raise ValueError("integration inputs alias")
    if _sha256(reference) != PINNED_PROJECT_SHA256:
        raise ValueError("reference project does not match pinned source")
    helper_path = Path(__file__).with_name("prepare-lab-bootstrap.py")
    spec = importlib.util.spec_from_file_location("kbht_prepare_lab", helper_path)
    helper = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(helper)
    expected = helper.apply_local_auth_transform(helper.remap_build_ext_text(reference.read_bytes().decode("utf-8")))
    if power_display:
        expected = helper.apply_power_display_transform(expected)
    if staged.read_bytes() != expected.encode("utf-8"):
        raise ValueError("staged project does not match expected prior transforms")
    if expected.count(SOCKET_REQUEST_PIN) != 1:
        raise ValueError("socket request pin count mismatch")
    hooked = expected.replace(SOCKET_REQUEST_PIN, SOCKET_REQUEST_PIN + "\n" + SOCKET_REQUEST_HOOK, 1)
    transformed = bridge_path.read_bytes() + b"\n" + integration_path.read_bytes() + b"\n" + hooked.encode("utf-8")
    staged.write_bytes(transformed)
    return hashlib.sha256(transformed).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    bridge = subparsers.add_parser("stage-inventory-bridge")
    bridge.add_argument("--stage-root", type=Path, required=True)
    bridge.add_argument("--patch", type=Path, required=True)
    bridge.add_argument("--reference-project", type=Path, required=True)
    integrate = subparsers.add_parser("integrate-inventory-bridge")
    integrate.add_argument("--stage-root", type=Path, required=True)
    integrate.add_argument("--input", type=Path, required=True)
    integrate.add_argument("--reference-project", type=Path, required=True)
    integrate.add_argument("--bridge", type=Path, required=True)
    integrate.add_argument("--integration", type=Path, required=True)
    integrate.add_argument("--power-display", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "stage-inventory-bridge":
            digest = stage_inventory_bridge(args.stage_root, args.patch, args.reference_project)
        else:
            digest = integrate_inventory_bridge(args.input, args.reference_project, args.bridge,
                                                 args.integration, stage_root=args.stage_root,
                                                 power_display=args.power_display)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(f"inventory_bridge_sha256={digest}")
    if args.command == "stage-inventory-bridge":
        print("inventory_bridge_target=assets/src/inventory-bridge.js")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

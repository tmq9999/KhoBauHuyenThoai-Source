"""Pin exact native consumer guards to a staged copy; never edit recovery input."""
import argparse
import hashlib
import importlib.util
import os
from pathlib import Path


def _module(name, filename):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def transform(source: str) -> str:
    replacements = (
        ('u.getServerInfo(e, function(e) {\ni.removeLoading();',
         'u.getServerInfo(e, function(e) {\ni.removeLoading();\n'
         'if (!window.kbhtNativeAvailability.hasServers(e)) {\n'
         't.selectServerItem = null; u.serverInfo = {serverList: [], players: []};\n'
         't.serverInfoNode.active = false; t.selectServerPanel.active = false;\n'
         'i.addHintPanel("Máy chủ chưa sẵn sàng"); return;\n}'),
        ('u._init(t, n, l, function(t) {\nvar n = e("serverMain").clientConfig.aliasUrl;',
         'u._init(t, n, l, function(t) {\n'
         'if (!window.kbhtNativeAvailability.gateAccepted(t)) {\n'
         'u.isConnected = false; u.isConnectingGate = false;\n'
         'u.receiveCb && u.receiveCb({code: 500, msg: "Không kết nối được máy chủ"});\n'
         'a.disconnect(); return;\n}\nvar n = e("serverMain").clientConfig.aliasUrl;'),
        ('var n = e("serverMain").clientConfig.aliasUrl;\na.init({\nhost: n ? n.connectorHostMap[t.port] : t.host,\nport: n ? n.connectorPortMap[t.port] : t.port,',
         'var n = window.kbhtNativeAvailability.connectorTarget(t, e("serverMain").clientConfig.aliasUrl);\n'
         'if (!n) { u.isConnected = false; u.isConnectingGate = false;\n'
         'u.receiveCb && u.receiveCb({code: 500, msg: "Địa chỉ máy chủ không hợp lệ"});\n'
         'a.disconnect(); return; }\na.init({\nhost: n.host,\nport: n.port,'),
        ('u.log(e, t);\nu.isConnected = !0;\nc && c();',
         'u.log(e, t);\nif (!window.kbhtNativeAvailability.entryAccepted(t)) {\n'
         'u.isConnected = false; u.isConnectingGate = false;\n'
         'u.receiveCb && u.receiveCb({code: 500, msg: "Phiên đăng nhập không hợp lệ"});\n'
         'a.disconnect(); return;\n}\nu.isConnectingGate = false;\nu.isConnected = !0;\nc && c();'),
        ('(!b[0].isSaleOut || !b[1].isSaleOut)',
         'window.kbhtNativeAvailability.shopBadge(b)'),
        ('for (var C in p) i.push({\nactivityName: d ? d.name : null,',
         'for (var C in p) if (n[C]) i.push({\nactivityName: d ? d.name : null,'),
    )
    for before, after in replacements:
        if source.count(before) != 1:
            raise ValueError('native consumer pin missing or duplicated')
        source = source.replace(before, after, 1)
    return source


def stage(staged_project: Path, reference: Path, patch: Path, stage_root: Path,
          *, power_display: bool = False) -> str:
    guards = _module('native_path_guards', 'stage-client-patches.py')
    root = guards._validate_stage(stage_root)
    staged = guards._require_plain_file(staged_project, 'staged project')
    reference = guards._require_plain_file(reference, 'reference')
    patch = guards._require_plain_file(patch, 'availability patch')
    if not guards._under(staged, root) or staged.stat().st_nlink != 1:
        raise ValueError('staged destination escapes root or is hardlinked')
    if any(os.path.samefile(a, b) for a, b in ((staged, reference), (staged, patch), (reference, patch))):
        raise ValueError('native availability inputs alias')
    raw = reference.read_bytes()
    if hashlib.sha256(raw).hexdigest() != guards.PINNED_PROJECT_SHA256:
        raise ValueError('reference source hash mismatch')
    prepare = _module('native_prior_transforms', 'prepare-lab-bootstrap.py')
    expected = prepare.apply_local_auth_transform(prepare.remap_build_ext_text(raw.decode('utf-8')))
    if power_display:
        expected = prepare.apply_power_display_transform(expected)
    if staged.read_bytes() != expected.encode('utf-8'):
        raise ValueError('staged predecessor mismatch')
    output = patch.read_bytes() + b'\n' + transform(expected).encode('utf-8')
    staged.write_bytes(output)
    return hashlib.sha256(output).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--patch', type=Path, required=True)
    parser.add_argument('--stage-root', type=Path, required=True)
    parser.add_argument('--power-display', action='store_true')
    args = parser.parse_args()
    try:
        digest = stage(args.input, args.reference, args.patch, args.stage_root, power_display=args.power_display)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print('native_availability_sha256=' + digest)


if __name__ == '__main__':
    main()

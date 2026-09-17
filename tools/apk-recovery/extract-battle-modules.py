"""Extract audited pure modules only; never evaluate the recovered application.

Run with --output pointing into ignored work/. The manifest preserves exact
source spans and hashes. Changing the source requires a new independent audit.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import stat

SOURCE_SHA256 = '9776b6e20978d5d911bc0abb85830820bac5a3bfb8db4e65a617c5d18646a818'
ALLOWLIST = frozenset('''actionManager action aiManager ai area baseBrain blackboard
brainService buff characterEvent character consts entity eventManager fightHandler
fightskill formula libBT missileAoe missileBrain missileGoAndBack missileLink
missileNormal missileTarget missileTimeTarget missileTime missile mobBrain mob
moveToEmptyPosition moveToTarget move mt_rand queue roleBrain role scheduler team
timer tryAndAdjust tryAttack util'''.split())
ADAPTERS = {'dataApi', 'battleMain', 'battle.msgHandler', 'serverConfig'}
HEADER = re.compile(r'^(?:"([^"\n]+)"|(\w+)): \[ function\(e, t, n\) \{\n', re.M)


def extract(path):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != SOURCE_SHA256:
        raise ValueError('recovered source hash mismatch')
    source = raw.decode('utf-8').replace('\r\n', '\n')
    headers = list(HEADER.finditer(source))
    selected = {'battle.' + name for name in ALLOWLIST} | {'underscore', 'emitter'}
    modules = {}
    for index, match in enumerate(headers):
        name = match.group(1) or match.group(2)
        if name not in selected:
            continue
        end = headers[index + 1].start() if index + 1 < len(headers) else len(source)
        block = source[match.end():end]
        boundary = block.rfind('\n}, {')
        if boundary < 0:
            raise ValueError('module boundary invalid')
        body = block[:boundary]
        dependencies = sorted(set(re.findall(r'\be\("([^"\n]+)"\)', body)))
        if set(dependencies) - selected - ADAPTERS:
            raise ValueError('unapproved module dependency')
        # These modules have no IO. Function/string timers in scheduler and
        # underscore are additionally disabled by VM codeGeneration:false.
        if re.search(r'\b(?:process|fetch|XMLHttpRequest|WebSocket|jsb)\b', body):
            raise ValueError('unexpected ambient capability')
        modules[name] = {
            'body': body,
            'sha256': hashlib.sha256(body.encode()).hexdigest(),
            'lineStart': source.count('\n', 0, match.start()) + 1,
            'lineEnd': source.count('\n', 0, match.end() + boundary) + 1,
            'dependencies': dependencies,
        }
    if set(modules) != selected:
        raise ValueError('allowlisted module missing')
    # battleMain includes UI lifecycle and Date.now battle entrypoints. Retain
    # only its exact pure initializer and exact explicit-seed RNG functions.
    start = source.index('var l = e("battle.mt_rand"), a = e("battle.consts"), i = {')
    end = source.index('var r = e("battle.fightHandler");', start)
    seed_start = source.index('i.setSeed = function(e) {', end)
    seed_end = source.index('i.smapBattle = function(', seed_start)
    body = source[start:end] + source[seed_start:seed_end]
    modules['battleMain'] = {'body': body,
        'sha256': hashlib.sha256(body.encode()).hexdigest(),
        'sourceRanges': [[source.count('\n', 0, start)+1, source.count('\n', 0, end)],
                         [source.count('\n', 0, seed_start)+1, source.count('\n', 0, seed_end)]],
        'dependencies': ['battle.mt_rand', 'battle.consts']}
    return {'format': 'kbht-battle-modules-v1', 'sourceSha256': SOURCE_SHA256,
            'modules': modules}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path('client-recovered/src/project.js'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    artifact = extract(args.source)
    candidate = args.output.absolute()
    for component in (candidate, *candidate.parents):
        if component.exists() or component.is_symlink():
            info = component.lstat()
            if component.is_symlink() or getattr(info, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400):
                parser.error('battle artifact path must not contain links')
    target = candidate.resolve()
    work = Path(__file__).resolve().parents[2] / 'work'
    if not target.is_relative_to(work) or target == work:
        parser.error('battle artifact output must be inside project work directory')
    payload = json.dumps(artifact, ensure_ascii=False, sort_keys=True).encode('utf-8')
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if not target.is_file() or target.stat().st_nlink != 1 or target.read_bytes() != payload:
            parser.error('refusing to overwrite different or linked battle artifact')
    else:
        with target.open('xb') as output:
            output.write(payload)
    print(json.dumps({'modules': len(artifact['modules']), 'sourceSha256': SOURCE_SHA256,
                      'artifactSha256': hashlib.sha256(payload).hexdigest()}))


if __name__ == '__main__':
    main()

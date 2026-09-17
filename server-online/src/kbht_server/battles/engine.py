"""Bounded recovered engine adapter for SERVER-OWNED snapshots only.

This is deliberately not a native route and never accepts client stats/results
as authority. Callers must load pinned content and owned persisted team first.
"""
import hashlib
import json
import os
import math
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading

ARTIFACT_SHA256 = '73a690818bc83f3857c7032cae8340f723963691efc2baa3194a7be788486168'
MAX_INPUT = 2_000_000
MAX_OUTPUT = 4_000_000


class BattleEngineError(ValueError):
    """Fixed non-sensitive computation error; no child trace or player payload."""


class RecoveredBattleEngine:
    def __init__(self, artifact, *, node=None, timeout=8):
        self.artifact = Path(artifact).resolve()
        self.node = node or shutil.which('node')
        self.timeout = min(max(float(timeout), 0.1), 10)

    def simulate_trusted(self, battle_input):
        try:
            payload = json.dumps(battle_input, allow_nan=False, separators=(',', ':')).encode()
        except (ValueError, TypeError, RecursionError):
            raise BattleEngineError('invalid battle input') from None
        if len(payload) > MAX_INPUT:
            raise BattleEngineError('battle input limit')
        if (not isinstance(battle_input, dict) or type(battle_input.get('actions')) is not list
                or len(battle_input['actions']) > 256):
            raise BattleEngineError('invalid manual actions')
        seed = battle_input.get('seed')
        if type(seed) is not int or not 1 <= seed <= 0xffffffff:
            raise BattleEngineError('invalid battle seed')
        try:
            if self.artifact.stat().st_size > 600_000:
                raise BattleEngineError('battle artifact invalid')
            artifact = self.artifact.read_bytes()
        except OSError:
            raise BattleEngineError('battle artifact unavailable') from None
        if hashlib.sha256(artifact).hexdigest() != ARTIFACT_SHA256:
            raise BattleEngineError('battle artifact hash mismatch')
        if not self.node:
            raise BattleEngineError('battle runtime unavailable')
        # No credentials, NODE_OPTIONS or inherited preload paths in the child.
        env = {key: os.environ[key] for key in ('SystemRoot', 'WINDIR') if key in os.environ}
        driver = Path(__file__).with_name('driver.cjs')
        try:
            with tempfile.TemporaryDirectory(prefix='kbht-battle-') as directory:
                # Copy verified bytes, avoiding a hash-check/read TOCTOU gap.
                staged = Path(directory) / 'modules.json'
                staged.write_bytes(artifact)
                child = subprocess.Popen([self.node, '--max-old-space-size=96', str(driver), str(staged)],
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    cwd=directory, env=env, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                output, errors = bytearray(), bytearray()
                overflow = threading.Event()
                def drain(stream, destination):
                    while chunk := stream.read(8192):
                        if len(destination) + len(chunk) > MAX_OUTPUT:
                            overflow.set()
                            child.kill()
                            break
                        destination.extend(chunk)
                readers = [threading.Thread(target=drain, args=(child.stdout, output), daemon=True),
                           threading.Thread(target=drain, args=(child.stderr, errors), daemon=True)]
                for reader in readers:
                    reader.start()
                def feed():
                    try:
                        child.stdin.write(payload)
                    except (BrokenPipeError, OSError):
                        pass
                    finally:
                        try:
                            child.stdin.close()
                        except OSError:
                            pass
                feeder = threading.Thread(target=feed, daemon=True)
                try:
                    feeder.start()
                    child.wait(timeout=self.timeout)
                except (subprocess.TimeoutExpired, BrokenPipeError):
                    child.kill()
                    child.wait()
                    raise BattleEngineError('battle execution limit') from None
                finally:
                    feeder.join(timeout=1)
                    for reader in readers:
                        reader.join(timeout=1)
                    child.stdout.close()
                    child.stderr.close()
                if overflow.is_set():
                    raise BattleEngineError('battle output limit')
                if child.returncode or errors:
                    raise BattleEngineError('battle computation rejected')
        except OSError:
            raise BattleEngineError('battle runtime unavailable') from None
        try:
            report = json.loads(output)
            if (report['format'] != 'kbht-battle-report-v1' or report['seed'] != seed
                    or report['smapId'] != battle_input.get('smapId')
                    or type(report['isWin']) is not bool or type(report['star']) is not int
                    or report['star'] not in range(4) or report['acceptedActions'] != battle_input['actions']
                    or not isinstance(report['zones'], list) or not report['zones']
                    or type(report['ticks']) is not int or not 0 < report['ticks'] <= 18000
                    or not isinstance(report['remainingRoles'], list)
                    or len(report['eventDigest']) != 64
                    or report['engineArtifactSha256'] != ARTIFACT_SHA256
                    or report['executionPolicy'] != 'smap-manual-tick-input-v1'
                    or report['inputSha256'] != hashlib.sha256(payload).hexdigest()
                    or (not report['isWin'] and report['star'] != 0)):
                raise ValueError()
            for role in report['remainingRoles']:
                for field in ('hp', 'maxHp', 'mp'):
                    if type(role[field]) not in (int, float) or not math.isfinite(role[field]) or role[field] < 0:
                        raise ValueError()
            json.dumps(report, allow_nan=False)
        except (ValueError, KeyError, TypeError):
            raise BattleEngineError('battle report invalid') from None
        return report

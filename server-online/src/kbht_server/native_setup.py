"""Explicit local native-onboarding activation, not gameplay/battle publication."""
import argparse
import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import stat
import subprocess
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import text
from kbht_server.content.native_players import (
    SOURCE_SHA, canonical, prepare_native_player_content, read_native_player_content,
    validate_policy,
)
from kbht_server.db.native_permissions import grant_native_runtime_access, validate_native_access, validate_role_name
from kbht_server.db.session import database_url, open_engine

POLICY_SHA = '18ba816a19a827d976818a26f0cd115613bb9aec3a98249bae83a3aabc03909e'
RUNTIME_ROLE = 'kbht_native_runtime'


def opening_spec(source, policy_path):
    source = Path(source).resolve(strict=True)
    policy = validate_policy(json.loads(Path(policy_path).read_text(encoding='utf-8')))
    policy_sha = hashlib.sha256(canonical(policy).encode()).hexdigest()
    if policy_sha != POLICY_SHA:
        raise ValueError('only the exact approved native-opening-v1 policy is accepted')
    definitions = read_native_player_content(source, SOURCE_SHA, policy)
    digest = hashlib.sha256(canonical({'definitions': definitions, 'policy': policy}).encode()).hexdigest()
    return {'source': source, 'policy': policy, 'definitions': definitions,
            'rules_sha256': digest,
            'id': uuid5(NAMESPACE_URL, f'kbht:native-opening-v1:{SOURCE_SHA}:{policy_sha}')}


def _target(connection, *, disposable=False):
    database, schema = connection.execute(text('SELECT current_database(),current_schema()')).one()
    accepted = (database == 'kbht_test' and re.fullmatch(r'kbht_t_[0-9a-f]{32}', schema or '')) if disposable else (database == 'kbht_dev' and schema == 'kbht_core')
    if not accepted:
        raise ValueError('native setup requires kbht_dev.kbht_core')
    if connection.execute(text('SELECT version_num FROM alembic_version')).scalars().all() != ['0014_native_players']:
        raise ValueError('native setup requires schema already at 0014_native_players')


def _existing(connection, spec, server_id, server_name):
    if type(server_id) is not int or not 1 <= server_id <= 2147483647:
        raise ValueError('positive PostgreSQL server id required')
    if (not isinstance(server_name, str) or not 1 <= len(server_name) <= 64 or
            server_name != server_name.strip() or any(ord(c) < 32 for c in server_name)):
        raise ValueError('explicit server name required')
    servers = connection.execute(text('SELECT * FROM game_servers WHERE id=:id OR name=:name'),
                                 {'id': server_id, 'name': server_name}).mappings().all()
    if servers and (len(servers) != 1 or servers[0]['id'] != server_id or
                    servers[0]['name'] != server_name or servers[0]['status'] != 'OPEN' or
                    servers[0]['active_content_version_id'] != spec['id'] or
                    servers[0]['business_timezone'] != 'Asia/Ho_Chi_Minh'):
        raise ValueError('refusing takeover of an existing different server')
    if connection.execute(text('SELECT EXISTS(SELECT 1 FROM players WHERE server_id=:id)'), {'id': server_id}).scalar_one():
        raise ValueError('activation requires no existing target-server players')
    release = connection.execute(text('SELECT * FROM content_versions WHERE id=:id'), {'id': spec['id']}).mappings().one_or_none()
    if release and (release['source_sha256'] != SOURCE_SHA or release['rules_sha256'] != spec['rules_sha256'] or
                    release['status'] not in ('DRAFT', 'PUBLISHED')):
        raise ValueError('opening release drift')
    saved = connection.execute(text('SELECT * FROM native_player_content WHERE content_version_id=:id'), {'id': spec['id']}).mappings().one_or_none()
    if saved and (saved['source_sha256'] != SOURCE_SHA or saved['rules_id'] != spec['policy']['rules_id'] or
                  saved['definition_sha256'] != spec['rules_sha256'] or saved['definitions'] != spec['definitions'] or
                  saved['policy'] != spec['policy']):
        raise ValueError('opening definitions or policy drift')
    if (release and release['status'] == 'PUBLISHED' and saved is None) or (servers and (release is None or release['status'] != 'PUBLISHED')):
        raise ValueError('incomplete existing opening release')
    # Refuse to turn a general content draft into an onboarding-only release.
    quote = connection.dialect.identifier_preparer.quote_identifier
    tables = connection.execute(text("""SELECT c.relname FROM pg_class c
        JOIN pg_namespace n ON n.oid=c.relnamespace
        JOIN pg_attribute a ON a.attrelid=c.oid
        WHERE n.nspname=current_schema() AND c.relkind='r'
          AND a.attname='content_version_id' AND NOT a.attisdropped
          AND c.relname <> 'native_player_content'""")).scalars()
    for table in tables:
        if connection.execute(text(f'SELECT EXISTS(SELECT 1 FROM {quote(table)} WHERE content_version_id=:id)'), {'id': spec['id']}).scalar_one():
            raise ValueError('opening release contains non-opening content or owned state')
    return release, bool(servers)


def activate_opening(connection, spec, server_id, server_name, *, disposable=False):
    """Caller owns transaction. Test escape only accepts a generated kbht_test schema."""
    _target(connection, disposable=disposable)
    connection.execute(text("SELECT pg_advisory_xact_lock(hashtextextended('kbht-native-opening-setup',0))"))
    # Administrative activation runs before player traffic. Prevent concurrent
    # player insertion, server takeover and content staging while checking.
    connection.execute(text('LOCK TABLE game_servers,players,content_versions IN SHARE ROW EXCLUSIVE MODE'))
    connection.execute(text('SELECT id FROM content_versions WHERE id=:id FOR UPDATE'), {'id': spec['id']})
    release, exists = _existing(connection, spec, server_id, server_name)
    if release is None:
        connection.execute(text("INSERT INTO content_versions(id,source_sha256,rules_sha256,status) VALUES (:id,:source,:rules,'DRAFT')"),
                           {'id': spec['id'], 'source': SOURCE_SHA, 'rules': spec['rules_sha256']})
    if release is None or release['status'] == 'DRAFT':
        prepared = prepare_native_player_content(connection, spec['id'], spec['source'], SOURCE_SHA, spec['policy'])
        if prepared['definition_sha256'] != spec['rules_sha256']:
            raise ValueError('opening digest verification failed')
        connection.execute(text("UPDATE content_versions SET status='PUBLISHED' WHERE id=:id AND status='DRAFT'"), {'id': spec['id']})
    if not exists:
        connection.execute(text("INSERT INTO game_servers(id,name,status,active_content_version_id) VALUES (:id,:name,'OPEN',:content)"),
                           {'id': server_id, 'name': server_name, 'content': spec['id']})
    return {'content_version_id': str(spec['id']), 'rules_sha256': spec['rules_sha256'],
            'server_id': server_id, 'scope': 'native-onboarding-only; battle/recruitment unavailable'}


def _scram(password, salt=None, iterations=4096):
    salt = salt or secrets.token_bytes(16)
    salted = hashlib.pbkdf2_hmac('sha256', password.encode('ascii'), salt, iterations)
    stored = hashlib.sha256(hmac.digest(salted, b'Client Key', 'sha256')).digest()
    server = hmac.digest(salted, b'Server Key', 'sha256')
    enc = lambda value: base64.b64encode(value).decode('ascii')
    return f'SCRAM-SHA-256${iterations}:{enc(salt)}${enc(stored)}:{enc(server)}'


def _credential_path(path):
    root = Path(__file__).resolve().parents[3]
    candidate = Path(path)
    if '..' in candidate.parts:
        raise ValueError('credential parent traversal is forbidden')
    candidate = candidate.absolute()
    # Do not resolve first: that would erase evidence of a linked ancestor.
    for component in (*reversed(candidate.parents), candidate):
        try:
            info = component.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
            raise ValueError('credential links/reparse paths are forbidden')
    target = candidate.resolve()
    if not target.is_relative_to(root / 'work') or target.parent == root:
        raise ValueError('runtime credential must be under ignored project work directory')
    if not target.parent.is_dir():
        raise ValueError('create the private credential directory explicitly first')
    result = subprocess.run(['git', 'check-ignore', '-q', '--', str(target)], cwd=root,
                            capture_output=True, check=False)
    if result.returncode != 0:
        raise ValueError('runtime credential path must be ignored')
    if target.exists():
        _private_credential(target)
    return target


def _private_credential(path):
    """Read-only validation: never repair an existing credential's ACL."""
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or
            getattr(info, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT):
        raise ValueError('credential must be a regular single-link file')
    if os.name != 'nt':
        if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600:
            raise ValueError('credential must be current-user owned mode0600')
        return
    # Use SID values, not localized account display names. The fixed script
    # reads only ACL metadata; the path is data in its environment, not code.
    script = r'''
$ErrorActionPreference='Stop'
$a=Get-Acl -LiteralPath $env:KBHT_CREDENTIAL_ACL_PATH
$sid=[System.Security.Principal.SecurityIdentifier]
$me=[System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value
$owner=$a.GetOwner($sid).Value
$rules=@($a.GetAccessRules($true,$true,$sid) | ForEach-Object {
  @{sid=$_.IdentityReference.Value; type=[int]$_.AccessControlType}
})
@{current=$me;owner=$owner;protected=$a.AreAccessRulesProtected;rules=$rules} | ConvertTo-Json -Compress -Depth 4
'''
    acl_environment = {k: v for k, v in os.environ.items() if k.casefold() != 'psmodulepath'}
    result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', script],
                            env={**acl_environment, 'KBHT_CREDENTIAL_ACL_PATH': str(path)},
                            capture_output=True, text=True, check=True)
    acl = json.loads(result.stdout)
    allowed = {acl['current'], 'S-1-5-18'}
    if (acl['owner'] != acl['current'] or not acl['protected'] or not acl['rules'] or
            any(rule['type'] != 0 or rule['sid'] not in allowed for rule in acl['rules']) or
            not any(rule['sid'] == acl['current'] for rule in acl['rules'])):
        raise ValueError('credential requires private current-user/SYSTEM ACL and current-user owner')


def _write_password(path, password):
    # No overwrite on failure/retry. On Windows restrict the empty file before
    # writing any secret; os.open(mode=0600) supplies the POSIX equivalent.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        if os.name == 'nt':
            identity = subprocess.run(['whoami', '/user', '/fo', 'csv', '/nh'], capture_output=True, text=True, check=True)
            sid = re.search(r'S-1-\d+(?:-\d+)+', identity.stdout)
            if sid is None:
                raise ValueError('cannot determine credential file owner')
            subprocess.run(['icacls', str(path), '/inheritance:r', '/grant:r', f'*{sid.group()}:(F)'], capture_output=True, check=True)
        _private_credential(path)
        with os.fdopen(fd, 'w', encoding='ascii') as stream:
            fd = None
            stream.write(password + '\n')
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        if fd is not None:
            os.close(fd)


def provision_runtime(connection, password_path, *, role=RUNTIME_ROLE):
    validate_role_name(role)
    path = _credential_path(password_path)
    exists = connection.execute(text('SELECT EXISTS(SELECT 1 FROM pg_roles WHERE rolname=:role)'), {'role': role}).scalar_one()
    if exists:
        validate_native_access(connection, role)
        if not connection.execute(text('SELECT rolcanlogin FROM pg_roles WHERE rolname=:role'), {'role': role}).scalar_one():
            raise ValueError('existing runtime role must have LOGIN; no role alteration')
        if not path.is_file() or path.stat().st_size > 256:
            raise ValueError('existing runtime role requires its existing credential file; no rotation')
        password = path.read_text(encoding='ascii').strip()
        verifier = connection.execute(text('SELECT rolpassword FROM pg_authid WHERE rolname=:role'), {'role': role}).scalar_one()
        match = re.fullmatch(r'SCRAM-SHA-256\$(\d+):([A-Za-z0-9+/=]+)\$[A-Za-z0-9+/=]+:[A-Za-z0-9+/=]+', verifier or '')
        if match is None or not 4096 <= int(match[1]) <= 100000 or not hmac.compare_digest(_scram(password, base64.b64decode(match[2]), int(match[1])), verifier):
            raise ValueError('runtime credential does not match existing role; no rotation')
    else:
        password = secrets.token_urlsafe(48)
        _write_password(path, password)
        verifier = _scram(password)
        # Only a client-side SCRAM verifier reaches SQL. Password never appears
        # in SQL, argv, logs or a return value. Safe fixed alphabet literal.
        try:
            # exec_driver_sql avoids SQLAlchemy treating SCRAM's colon as a
            # named bind. Suppress chained SQL exceptions at this boundary.
            connection.exec_driver_sql(f"CREATE ROLE {role} LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD '{verifier}'")
        except Exception:
            raise ValueError('native runtime role creation failed; credential retained') from None
    grant_native_runtime_access(connection, role)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--environment', required=True, choices=['development'])
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--policy', type=Path, required=True)
    parser.add_argument('--server-id', type=int, required=True)
    parser.add_argument('--server-name', required=True)
    parser.add_argument('--runtime-password-file', type=Path, required=True)
    parser.add_argument('--apply', action='store_true', help='explicitly create native role/release/server; never migrate')
    args = parser.parse_args(argv)
    engine = None
    try:
        spec = opening_spec(args.source, args.policy)
        _credential_path(args.runtime_password_file)
        engine = open_engine(database_url(args.environment), schema='kbht_core')
        with engine.begin() as connection:
            if not args.apply:
                connection.execute(text('SET TRANSACTION READ ONLY'))
                _target(connection)
                _existing(connection, spec, args.server_id, args.server_name)
                result = {'status': 'PREVIEW_ONLY', 'content_version_id': str(spec['id']),
                          'scope': 'native-onboarding-only; no battle/recruitment publication'}
            else:
                _target(connection)
                # Refuse content/server drift before touching credential file.
                _existing(connection, spec, args.server_id, args.server_name)
                provision_runtime(connection, args.runtime_password_file)
                result = activate_opening(connection, spec, args.server_id, args.server_name)
                result['status'] = 'APPLIED_NOT_NATIVE_CONFIRMED'
        print(json.dumps(result, sort_keys=True))
        return 0
    except Exception:
        # Never print SQLAlchemy/driver exceptions: SQL can contain verifier
        # material. An exclusive credential file is deliberately retained after
        # rollback for operator reconciliation, never overwritten automatically.
        print('Native setup refused or failed; no secret details emitted. Inspect target/schema/policy/ACLs and retained credential file before retry.')
        return 1
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == '__main__':
    raise SystemExit(main())

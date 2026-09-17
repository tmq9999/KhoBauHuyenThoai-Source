"""Separate native-onboarding role; never widens the gameplay role policy."""
import re

from sqlalchemy import text
from .permissions import READ_TABLES, INSERT_TABLES, UPDATE_COLUMNS

NATIVE_READ = (*READ_TABLES, 'accounts', 'sessions', 'native_player_content',
               'native_player_profiles', 'native_owned_roles', 'native_role_skills',
               'native_role_equipment', 'native_map_progress')
NATIVE_INSERT = (*INSERT_TABLES, 'accounts', 'sessions', 'players', 'wallets',
                 'native_player_profiles', 'native_owned_roles',
                 'native_role_skills', 'native_role_equipment')
TUTORIAL_READ = ('native_tutorial_content', 'native_tutorial_claims')
TUTORIAL_INSERT = ('native_tutorial_claims',)
NATIVE_UPDATE = {key: set(value) for key, value in UPDATE_COLUMNS.items()}
NATIVE_UPDATE.update({
    'accounts': {'password_hash'}, 'sessions': {'revoked_at'},
    'players': {'name', 'version', 'updated_at'},
    # FOR SHARE needs UPDATE on one column. The statement-level immutable
    # trigger forbids actual UPDATE, even a no-op, on this content table.
    'native_player_content': {'content_version_id'},
    'native_player_profiles': {'first_rename_completed', 'next_action_recover_ms',
                               'next_skill_recover_ms'},
})
NATIVE_SEQUENCES = {'inventory_items_id_seq', 'native_player_id_seq'}


def validate_role_name(role):
    if type(role) is not str or not re.fullmatch(r'kbht_native_(?:runtime|t_[0-9a-f]{32})', role):
        raise ValueError('dedicated native runtime role required')


def validate_native_access(connection, role):
    """Read-only fail-closed audit before additive grants, including PUBLIC ACLs."""
    validate_role_name(role)
    row = connection.execute(text('''
        SELECT r.oid,r.rolsuper,r.rolcreatedb,r.rolcreaterole,r.rolreplication,
          r.rolbypassrls,r.rolinherit,
          EXISTS(SELECT 1 FROM pg_auth_members WHERE member=r.oid) AS membership,
          EXISTS(SELECT 1 FROM pg_shdepend WHERE refclassid='pg_authid'::regclass
                 AND refobjid=r.oid AND deptype='o') AS owner
        FROM pg_roles r WHERE rolname=:role
    '''), {'role': role}).mappings().one_or_none()
    if row is None or any(row[k] for k in row if k != 'oid'):
        raise ValueError('native runtime requires unprivileged NOINHERIT non-owner role')
    database, schema = connection.execute(text('SELECT current_database(),current_schema()')).one()
    if not ((database == 'kbht_dev' and schema == 'kbht_core') or
            (database == 'kbht_test' and re.fullmatch(r'kbht_t_[0-9a-f]{32}', schema or ''))):
        raise ValueError('native role requires explicit local development or generated test schema')
    if connection.execute(text("SELECT has_database_privilege(:role,current_database(),'CREATE')"), {'role': role}).scalar_one():
        raise ValueError('native role has database DDL rights')
    if connection.execute(text("""SELECT EXISTS(SELECT 1 FROM pg_namespace
        WHERE nspname !~ '^pg_' AND nspname <> 'information_schema'
        AND has_schema_privilege(:role,oid,'CREATE'))"""), {'role': role}).scalar_one():
        raise ValueError('native role has schema DDL rights')
    for acl in connection.execute(text('''
        SELECT n.nspname,c.relname,c.relkind,a.privilege_type,a.is_grantable
        FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        CROSS JOIN LATERAL aclexplode(c.relacl) a
        WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'
          AND a.grantee IN (0,:oid)
    '''), {'oid': row['oid']}).mappings():
        table, privilege = acl['relname'], acl['privilege_type']
        allowed = acl['nspname'] == schema and (
            (table in (*NATIVE_READ, *TUTORIAL_READ) and privilege == 'SELECT') or
            (table in (*NATIVE_INSERT, *TUTORIAL_INSERT) and privilege == 'INSERT') or
            (table in NATIVE_SEQUENCES and acl['relkind'] == 'S' and privilege == 'USAGE'))
        if not allowed or acl['is_grantable']:
            raise ValueError('native role or PUBLIC has excess relation privileges')
    for acl in connection.execute(text('''
        SELECT n.nspname,c.relname,a.attname,x.privilege_type,x.is_grantable
        FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid
        JOIN pg_namespace n ON n.oid=c.relnamespace
        CROSS JOIN LATERAL aclexplode(a.attacl) x
        WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'
          AND x.grantee IN (0,:oid)
    '''), {'oid': row['oid']}).mappings():
        if (acl['nspname'] != schema or acl['privilege_type'] != 'UPDATE' or
                acl['is_grantable'] or acl['attname'] not in NATIVE_UPDATE.get(acl['relname'], set())):
            raise ValueError('native role or PUBLIC has excess column privileges')
    if connection.execute(text('''SELECT EXISTS(
        SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
        WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'
          AND p.prosecdef AND has_function_privilege(:role,p.oid,'EXECUTE'))
    '''), {'role': role}).scalar_one():
        raise ValueError('native role can execute a security-definer routine')
    if connection.execute(text('''SELECT EXISTS(
        SELECT 1 FROM pg_default_acl d CROSS JOIN LATERAL aclexplode(d.defaclacl) a
        WHERE a.grantee IN (0,:oid) AND d.defaclobjtype IN ('r','S','n'))
    '''), {'oid': row['oid']}).scalar_one():
        raise ValueError('native role or PUBLIC has additive default privileges')
    return schema


def grant_native_runtime_access(connection, role):
    schema = validate_native_access(connection, role)
    quote = connection.dialect.identifier_preparer.quote_identifier
    target, namespace = quote(role), quote(schema)
    connection.execute(text(f'GRANT USAGE ON SCHEMA {namespace} TO {target}'))
    for privilege, tables in (('SELECT', NATIVE_READ), ('INSERT', NATIVE_INSERT)):
        for table in tables:
            connection.execute(text(f'GRANT {privilege} ON {namespace}.{quote(table)} TO {target}'))
    for table, columns in NATIVE_UPDATE.items():
        names = ','.join(quote(c) for c in sorted(columns))
        connection.execute(text(f'GRANT UPDATE ({names}) ON {namespace}.{quote(table)} TO {target}'))
    for sequence in sorted(NATIVE_SEQUENCES):
        connection.execute(text(f'GRANT USAGE ON SEQUENCE {namespace}.{quote(sequence)} TO {target}'))


def grant_native_tutorial_access(connection, role):
    """Explicit additive role upgrade after0015, no definition or claim edits."""
    schema = validate_native_access(connection, role)
    if connection.execute(text('SELECT version_num FROM alembic_version')).scalar_one() != '0015_native_tutorial':
        raise ValueError('tutorial grants require schema0015')
    quote = connection.dialect.identifier_preparer.quote_identifier
    target, namespace = quote(role), quote(schema)
    for privilege, tables in (('SELECT', TUTORIAL_READ), ('INSERT', TUTORIAL_INSERT)):
        for table in tables:
            connection.execute(text(f'GRANT {privilege} ON {namespace}.{quote(table)} TO {target}'))

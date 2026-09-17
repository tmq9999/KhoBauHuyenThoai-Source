"""Explicit table privileges for a dedicated, non-owner runtime role."""

import re

from sqlalchemy import text
from sqlalchemy.engine import Connection

READ_TABLES = (
    "players", "game_servers", "content_versions", "item_definitions", "wallets",
    "ledger_transactions", "ledger_postings", "wallet_ledger", "command_receipts",
    "inventory_items", "inventory_ledger", "reward_grants", "reward_items",
    "reward_currencies", "outbox_events", "worker_receipts", "outbox_deliveries", "alembic_version",
    "fixed_box_definitions", "fixed_box_rewards",
)
INSERT_TABLES = (
    "ledger_transactions", "ledger_postings", "wallet_ledger", "command_receipts",
    "inventory_items", "inventory_ledger", "reward_grants", "reward_items",
    "reward_currencies", "outbox_events", "worker_receipts", "outbox_deliveries",
)
UPDATE_COLUMNS = {
    "players": {"version", "updated_at"},
    "wallets": {"balance", "version", "updated_at"},
    "inventory_items": {"quantity", "version", "updated_at"},
    "game_servers": {"id"},
    "content_versions": {"id"},
    "item_definitions": {"content_version_id"},
    "outbox_events": {"id"},
    "outbox_deliveries": {"status", "attempts", "lease_token", "lease_expires_at",
                          "next_attempt_at", "last_error_code", "updated_at"},
}


def grant_runtime_access(connection: Connection, role: str) -> None:
    if type(role) is not str or not re.fullmatch(r"kbht_(?:runtime|test_runtime_[0-9a-f]{32})", role):
        raise ValueError("use a dedicated kbht_runtime role")
    row = connection.execute(text("""
        SELECT r.oid, r.rolsuper, r.rolcreatedb, r.rolcreaterole, r.rolreplication, r.rolbypassrls, r.rolinherit,
          EXISTS (SELECT 1 FROM pg_auth_members m WHERE m.member = r.oid) AS has_membership,
          (SELECT nspname FROM pg_namespace WHERE nspname = current_schema()) AS schema,
          EXISTS (SELECT 1 FROM pg_namespace n WHERE n.nspowner = r.oid) AS owns_schema,
          EXISTS (SELECT 1 FROM pg_database d WHERE d.datdba = r.oid) AS owns_database,
          EXISTS (SELECT 1 FROM pg_class c WHERE c.relowner = r.oid) AS owns_relation
        FROM pg_roles r WHERE r.rolname = :role
    """), {"role": role}).mappings().one_or_none()
    if not row or any(row[key] for key in (
        "rolsuper", "rolcreatedb", "rolcreaterole", "rolreplication", "rolbypassrls",
        "has_membership", "owns_schema", "owns_database", "owns_relation", "rolinherit",
    )):
        raise ValueError("runtime requires a dedicated non-owner, unprivileged role")
    schema = row["schema"]
    if not schema or not re.fullmatch(r"kbht_(?:core|t_[0-9a-f]{32})", schema):
        raise ValueError("runtime grant requires the explicit KBHT schema")
    if connection.execute(text("SELECT current_database()")).scalar_one() not in {"kbht_dev", "kbht_test"}:
        raise ValueError("runtime grant requires the explicit lab database")
    if connection.execute(text("SELECT has_schema_privilege(:role, current_schema(), 'CREATE')"), {"role": role}).scalar_one():
        raise ValueError("runtime role has excess schema privileges")
    # GRANT is additive. Refuse pre-existing excessive grants instead of silently retaining them.
    acl_rows = connection.execute(text("""
        SELECT c.relname, c.relkind, acl.privilege_type, acl.is_grantable
        FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        CROSS JOIN LATERAL aclexplode(c.relacl) acl
        WHERE n.nspname = current_schema() AND acl.grantee IN (0, :oid)
    """), {"oid": row["oid"]}).mappings()
    for acl in acl_rows:
        table, privilege = acl["relname"], acl["privilege_type"]
        allowed = ((table in READ_TABLES and privilege == "SELECT") or
                   (table in INSERT_TABLES and privilege == "INSERT") or
                   (table == "inventory_items_id_seq" and acl["relkind"] == "S" and privilege == "USAGE"))
        if not allowed or acl["is_grantable"]:
            raise ValueError("runtime role has excess relation privileges")
    column_acls = connection.execute(text("""
        SELECT c.relname, a.attname, acl.privilege_type, acl.is_grantable
        FROM pg_attribute a JOIN pg_class c ON c.oid = a.attrelid
        JOIN pg_namespace n ON n.oid = c.relnamespace
        CROSS JOIN LATERAL aclexplode(a.attacl) acl
        WHERE n.nspname = current_schema() AND acl.grantee IN (0, :oid)
    """), {"oid": row["oid"]}).mappings()
    for acl in column_acls:
        if (acl["privilege_type"] != "UPDATE" or acl["is_grantable"] or
                acl["attname"] not in UPDATE_COLUMNS.get(acl["relname"], set())):
            raise ValueError("runtime role has excess column privileges")
    quoted_role = connection.dialect.identifier_preparer.quote_identifier(role)
    quoted_schema = connection.dialect.identifier_preparer.quote_identifier(schema)
    def grant(privilege, table):
        connection.execute(text(f'GRANT {privilege} ON {quoted_schema}."{table}" TO {quoted_role}'))
    connection.execute(text(f"GRANT USAGE ON SCHEMA {quoted_schema} TO {quoted_role}"))
    for table in READ_TABLES:
        grant("SELECT", table)
    for table in INSERT_TABLES:
        grant("INSERT", table)
    # PostgreSQL row locks require UPDATE on a column; immutable guards protect these.
    for table, columns in UPDATE_COLUMNS.items():
        grant(f"UPDATE ({', '.join(sorted(columns))})", table)
    connection.execute(text(f'GRANT USAGE ON SEQUENCE {quoted_schema}.inventory_items_id_seq TO {quoted_role}'))

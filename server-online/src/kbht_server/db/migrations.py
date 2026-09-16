from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def apply_migrations(engine: Engine) -> str:
    """Apply the checked-in core schema to the already validated target."""
    with engine.begin() as connection:
        connection.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(current_database() || current_schema(), 0))"))
        names = inspect(connection).get_table_names()
        if names and "alembic_version" not in names:
            raise RuntimeError("Refusing to stamp an unversioned schema; use a fresh isolated schema")
        cfg = Config()
        cfg.set_main_option("script_location", str(Path(__file__).with_name("alembic")))
        cfg.attributes["connection"] = connection
        command.upgrade(cfg, "head")
        revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
    return revision


def check_invariants(engine: Engine) -> dict[str, int]:
    queries = {
        "wallet_mismatches": """
            SELECT count(*) FROM wallets w FULL JOIN
              (SELECT player_id, currency, sum(delta) AS total FROM wallet_ledger GROUP BY player_id, currency) l
              USING (player_id, currency)
            WHERE w.player_id IS NULL OR w.balance != coalesce(l.total, 0)
              OR w.balance < 0 OR w.balance > 9007199254740991
        """,
        "unbalanced_transactions": """
            SELECT count(*) FROM ledger_transactions t WHERE
              NOT EXISTS (SELECT 1 FROM ledger_postings p WHERE p.transaction_id = t.id)
              OR EXISTS (SELECT 1 FROM ledger_postings p WHERE p.transaction_id = t.id
                         GROUP BY p.currency HAVING sum(p.delta) != 0)
        """,
        "posting_mismatches": """
            SELECT count(*) FROM wallet_ledger l FULL JOIN
              (SELECT * FROM ledger_postings WHERE account_key LIKE 'player:%') p
              ON p.transaction_id = l.transaction_id AND p.line_no = l.line_no
            WHERE l.id IS NULL OR p.transaction_id IS NULL OR l.delta != p.delta
              OR l.currency != p.currency OR p.account_key != 'player:' || l.player_id::text
        """,
        "orphan_receipts": """
            SELECT count(*) FROM command_receipts r LEFT JOIN players p ON p.id = r.player_id
            WHERE p.id IS NULL OR r.aggregate_version > p.version
        """,
        "inventory_mismatches": """
            SELECT count(*) FROM inventory_items i FULL JOIN
              (SELECT inventory_id, sum(delta) total, max(inventory_version) version,
                      count(*) entries FROM inventory_ledger GROUP BY inventory_id) l
              ON i.id = l.inventory_id
            LEFT JOIN item_definitions d ON d.content_version_id = i.content_version_id AND d.kind_id = i.kind_id
            WHERE i.id IS NULL OR l.inventory_id IS NULL OR i.quantity != l.total
              OR i.version != l.version OR l.entries != l.version
              OR i.quantity < 0 OR i.quantity > d.stack_limit OR d.kind_id IS NULL
        """,
        "inventory_history_mismatches": """
            SELECT count(*) FROM (
              SELECT quantity_after, sum(delta) OVER (PARTITION BY inventory_id ORDER BY inventory_version) running_total
              FROM inventory_ledger
            ) history WHERE quantity_after != running_total
        """,
        "reward_item_mismatches": """
            SELECT count(*) FROM reward_items r FULL JOIN
              (SELECT reward_grant_id, kind_id, sum(delta) quantity FROM inventory_ledger
               WHERE reward_grant_id IS NOT NULL GROUP BY reward_grant_id, kind_id) l
              ON r.grant_id = l.reward_grant_id AND r.kind_id = l.kind_id
            WHERE r.grant_id IS NULL OR l.reward_grant_id IS NULL OR r.quantity != l.quantity
        """,
        "reward_currency_mismatches": """
            SELECT count(*) FROM reward_currencies r FULL JOIN
              (SELECT g.id AS grant_id, w.currency, sum(w.delta) quantity
               FROM reward_grants g JOIN wallet_ledger w
                 ON w.player_id = g.player_id AND w.command_id = g.command_id
                   AND w.reason = 'reward:' || g.id::text
               GROUP BY g.id, w.currency) l
              ON r.grant_id = l.grant_id AND r.currency = l.currency
            WHERE r.grant_id IS NULL OR l.grant_id IS NULL OR r.quantity != l.quantity
        """,
    }
    with engine.connect().execution_options(isolation_level="REPEATABLE READ") as connection:
        with connection.begin():
            connection.execute(text("SET TRANSACTION READ ONLY"))
            result = {key: int(connection.execute(text(query)).scalar_one()) for key, query in queries.items()}
    if any(result.values()):
        raise RuntimeError(f"database invariants failed: {result}")
    return result

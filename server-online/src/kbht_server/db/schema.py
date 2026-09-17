from __future__ import annotations

from sqlalchemy import BigInteger, CheckConstraint, Column, DateTime, ForeignKey, ForeignKeyConstraint, Identity, Integer, MetaData, String, Table, Text, UniqueConstraint, UUID, func
from sqlalchemy.dialects.postgresql import JSONB

metadata = MetaData()

content_versions = Table(
    "content_versions", metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("source_sha256", String(64), nullable=False),
    Column("rules_sha256", String(64), nullable=False),
    Column("status", String(16), nullable=False),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    CheckConstraint("status IN ('DRAFT', 'VALIDATED', 'PUBLISHED', 'RETIRED')", name="ck_content_versions_status"),
)

game_servers = Table(
    "game_servers", metadata,
    Column("id", Integer, primary_key=True),
    Column("name", String(64), nullable=False, unique=True),
    Column("status", String(16), nullable=False, server_default="MAINTENANCE"),
    Column("active_content_version_id", UUID(as_uuid=True), ForeignKey("content_versions.id")),
    Column("business_timezone", String(64), nullable=False, server_default="Asia/Ho_Chi_Minh"),
    CheckConstraint("status IN ('MAINTENANCE', 'OPEN', 'CLOSED')", name="ck_game_servers_status"),
)

accounts = Table(
    "accounts", metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("normalized_login", String(128), nullable=False, unique=True),
    Column("password_hash", Text, nullable=False),
    Column("status", String(16), nullable=False, server_default="ACTIVE"),
    CheckConstraint("status IN ('ACTIVE', 'LOCKED')", name="ck_accounts_status"),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
)

players = Table(
    "players", metadata,
    Column("id", BigInteger, primary_key=True),
    Column("account_id", UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
    Column("server_id", Integer, ForeignKey("game_servers.id"), nullable=False),
    Column("name", String(64), nullable=False),
    Column("version", Integer, nullable=False, server_default="0"),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    Column("updated_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    UniqueConstraint("account_id", "server_id", name="uq_players_account_server"),
    CheckConstraint("version >= 0", name="ck_players_version_nonnegative"),
)

wallets = Table(
    "wallets", metadata,
    Column("player_id", BigInteger, ForeignKey("players.id", ondelete="CASCADE"), primary_key=True),
    Column("currency", String(32), primary_key=True),
    Column("balance", BigInteger, nullable=False, server_default="0"),
    Column("version", Integer, nullable=False, server_default="0"),
    Column("updated_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    CheckConstraint("balance BETWEEN 0 AND 9007199254740991", name="ck_wallets_balance_nonnegative"),
    CheckConstraint("version >= 0", name="ck_wallets_version_nonnegative"),
)

ledger_transactions = Table(
    "ledger_transactions", metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("player_id", BigInteger, ForeignKey("players.id", ondelete="CASCADE"), nullable=False),
    Column("command_id", UUID(as_uuid=True), nullable=False),
    Column("reason", String(160), nullable=False),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    UniqueConstraint("player_id", "command_id", name="uq_ledger_transactions_command"),
)

ledger_postings = Table(
    "ledger_postings", metadata,
    Column("transaction_id", UUID(as_uuid=True), ForeignKey("ledger_transactions.id"), primary_key=True),
    Column("line_no", Integer, primary_key=True),
    Column("currency", String(32), nullable=False),
    Column("account_key", String(80), nullable=False),
    Column("delta", BigInteger, nullable=False),
)

command_receipts = Table(
    "command_receipts", metadata,
    Column("player_id", BigInteger, ForeignKey("players.id", ondelete="CASCADE"), primary_key=True),
    Column("command_id", UUID(as_uuid=True), primary_key=True),
    Column("route", String(160), nullable=False),
    Column("payload_hash", String(64), nullable=False),
    Column("result_json", JSONB, nullable=False),
    Column("aggregate_version", Integer, nullable=False),
    Column("status", String(16), nullable=False),
    Column("content_version_id", UUID(as_uuid=True), ForeignKey("content_versions.id"), nullable=False),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    CheckConstraint("status IN ('COMMITTED')", name="ck_command_receipts_status"),
)

wallet_ledger = Table(
    "wallet_ledger", metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("player_id", BigInteger, ForeignKey("players.id", ondelete="CASCADE"), nullable=False),
    Column("currency", String(32), nullable=False),
    Column("delta", BigInteger, nullable=False),
    Column("balance_after", BigInteger, nullable=False),
    Column("reason", String(160), nullable=False),
    Column("command_id", UUID(as_uuid=True), nullable=False),
    Column("transaction_id", UUID(as_uuid=True), ForeignKey("ledger_transactions.id", ondelete="CASCADE"), nullable=False),
    Column("line_no", Integer, nullable=False),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    UniqueConstraint("player_id", "currency", "command_id", "reason", name="uq_wallet_ledger_command_reason"),
    UniqueConstraint("transaction_id", "line_no", name="uq_wallet_ledger_transaction_line"),
    ForeignKeyConstraint(["transaction_id", "line_no"], ["ledger_postings.transaction_id", "ledger_postings.line_no"]),
    CheckConstraint("balance_after >= 0", name="ck_wallet_ledger_balance_nonnegative"),
)

outbox_events = Table(
    "outbox_events", metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("player_id", BigInteger, ForeignKey("players.id", ondelete="CASCADE"), nullable=False),
    Column("command_id", UUID(as_uuid=True), nullable=False),
    Column("event_type", String(160), nullable=False),
    Column("body", JSONB, nullable=False),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
)

worker_receipts = Table(
    "worker_receipts", metadata,
    Column("consumer", String(80), primary_key=True),
    Column("event_id", UUID(as_uuid=True), ForeignKey("outbox_events.id"), primary_key=True, index=True),
    Column("processed_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    CheckConstraint("length(consumer) > 0", name="ck_worker_receipts_consumer"),
)

outbox_deliveries = Table(
    "outbox_deliveries", metadata,
    Column("consumer", String(80), primary_key=True),
    Column("event_id", UUID(as_uuid=True), ForeignKey("outbox_events.id"), primary_key=True),
    Column("status", String(16), nullable=False, server_default="READY"),
    Column("attempts", Integer, nullable=False, server_default="0"),
    Column("max_attempts", Integer, nullable=False, server_default="5"),
    Column("lease_token", UUID(as_uuid=True)),
    Column("lease_expires_at", DateTime(timezone=True)),
    Column("next_attempt_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    Column("last_error_code", String(64)),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    Column("updated_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    CheckConstraint("status IN ('READY', 'LEASED', 'DONE', 'RETRY', 'DEAD')", name="ck_outbox_delivery_status"),
    CheckConstraint("attempts BETWEEN 0 AND 100", name="ck_outbox_delivery_attempts"),
    CheckConstraint("max_attempts BETWEEN 1 AND 100 AND attempts <= max_attempts", name="ck_outbox_delivery_budget"),
    CheckConstraint("(status = 'LEASED' AND lease_token IS NOT NULL AND lease_expires_at IS NOT NULL) OR "
                    "(status != 'LEASED' AND lease_token IS NULL AND lease_expires_at IS NULL)", name="ck_outbox_delivery_lease"),
)

item_definitions = Table(
    "item_definitions", metadata,
    Column("content_version_id", UUID(as_uuid=True), ForeignKey("content_versions.id"), primary_key=True),
    Column("kind_id", BigInteger, primary_key=True),
    Column("stack_limit", BigInteger, nullable=False),
    CheckConstraint("kind_id BETWEEN 1 AND 9007199254740991", name="ck_item_definition_id"),
    CheckConstraint("stack_limit BETWEEN 1 AND 9007199254740991", name="ck_item_stack_limit"),
)

inventory_items = Table(
    "inventory_items", metadata,
    Column("id", BigInteger, Identity(start=10001, maxvalue=9007199254740991), primary_key=True),
    Column("player_id", BigInteger, ForeignKey("players.id"), nullable=False),
    Column("content_version_id", UUID(as_uuid=True), nullable=False),
    Column("kind_id", BigInteger, nullable=False),
    Column("stack_key", String(64), nullable=False),
    Column("quantity", BigInteger, nullable=False),
    Column("version", BigInteger, nullable=False),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    Column("updated_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    ForeignKeyConstraint(["content_version_id", "kind_id"], ["item_definitions.content_version_id", "item_definitions.kind_id"]),
    UniqueConstraint("player_id", "kind_id", "stack_key", name="uq_inventory_stack"),
    UniqueConstraint("id", "player_id", "kind_id", name="uq_inventory_owner_kind"),
    CheckConstraint("quantity BETWEEN 0 AND 9007199254740991", name="ck_inventory_quantity"),
    CheckConstraint("version BETWEEN 1 AND 9007199254740991", name="ck_inventory_version"),
)

reward_grants = Table(
    "reward_grants", metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("player_id", BigInteger, ForeignKey("players.id"), nullable=False),
    Column("command_id", UUID(as_uuid=True), nullable=False),
    Column("content_version_id", UUID(as_uuid=True), ForeignKey("content_versions.id"), nullable=False),
    Column("source_type", String(64), nullable=False),
    Column("source_id", UUID(as_uuid=True), nullable=False),
    Column("payload_hash", String(64), nullable=False),
    Column("result_json", JSONB, nullable=False),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    UniqueConstraint("player_id", "source_type", "source_id", name="uq_reward_source"),
    UniqueConstraint("id", "content_version_id", name="uq_reward_content"),
    UniqueConstraint("id", "player_id", name="uq_reward_owner"),
    ForeignKeyConstraint(["player_id", "command_id"], ["command_receipts.player_id", "command_receipts.command_id"],
                         deferrable=True, initially="DEFERRED"),
)

inventory_ledger = Table(
    "inventory_ledger", metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("inventory_id", BigInteger, nullable=False),
    Column("player_id", BigInteger, nullable=False),
    Column("kind_id", BigInteger, nullable=False),
    Column("command_id", UUID(as_uuid=True), nullable=False),
    Column("content_version_id", UUID(as_uuid=True), nullable=False),
    Column("delta", BigInteger, nullable=False),
    Column("quantity_after", BigInteger, nullable=False),
    Column("inventory_version", BigInteger, nullable=False),
    Column("reason", String(160), nullable=False),
    Column("source_type", String(64), nullable=False),
    Column("source_id", UUID(as_uuid=True), nullable=False),
    Column("reward_grant_id", UUID(as_uuid=True)),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    ForeignKeyConstraint(["inventory_id", "player_id", "kind_id"], ["inventory_items.id", "inventory_items.player_id", "inventory_items.kind_id"]),
    ForeignKeyConstraint(["content_version_id", "kind_id"], ["item_definitions.content_version_id", "item_definitions.kind_id"]),
    ForeignKeyConstraint(["player_id", "command_id"], ["command_receipts.player_id", "command_receipts.command_id"],
                         deferrable=True, initially="DEFERRED"),
    ForeignKeyConstraint(["reward_grant_id", "player_id"], ["reward_grants.id", "reward_grants.player_id"],
                         deferrable=True, initially="DEFERRED"),
    UniqueConstraint("inventory_id", "inventory_version", name="uq_inventory_ledger_version"),
    CheckConstraint("delta != 0 AND delta BETWEEN -9007199254740991 AND 9007199254740991", name="ck_inventory_delta"),
    CheckConstraint("quantity_after BETWEEN 0 AND 9007199254740991", name="ck_inventory_after"),
    CheckConstraint("inventory_version BETWEEN 1 AND 9007199254740991", name="ck_inventory_ledger_version"),
)

reward_items = Table(
    "reward_items", metadata,
    Column("grant_id", UUID(as_uuid=True), primary_key=True),
    Column("kind_id", BigInteger, primary_key=True),
    Column("content_version_id", UUID(as_uuid=True), nullable=False),
    Column("quantity", BigInteger, nullable=False),
    ForeignKeyConstraint(["grant_id", "content_version_id"], ["reward_grants.id", "reward_grants.content_version_id"]),
    ForeignKeyConstraint(["content_version_id", "kind_id"], ["item_definitions.content_version_id", "item_definitions.kind_id"]),
    CheckConstraint("quantity BETWEEN 1 AND 9007199254740991", name="ck_reward_item_quantity"),
)

reward_currencies = Table(
    "reward_currencies", metadata,
    Column("grant_id", UUID(as_uuid=True), ForeignKey("reward_grants.id"), primary_key=True),
    Column("currency", String(32), primary_key=True),
    Column("quantity", BigInteger, nullable=False),
    CheckConstraint("quantity BETWEEN 1 AND 9007199254740991", name="ck_reward_currency_quantity"),
)

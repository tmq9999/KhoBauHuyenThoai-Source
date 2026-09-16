"""Inventory ownership, item ledger and unique reward sources."""

from pathlib import Path

from alembic import op

revision = "0003_inventory_rewards"
down_revision = "0002_worker_receipts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    folder = Path(__file__).parent
    for filename in ("0003_tables.sql", "0003_guards.sql"):
        op.get_bind().exec_driver_sql((folder / filename).read_text(encoding="ascii"))


def downgrade() -> None:
    raise RuntimeError("Destructive downgrade disabled; restore into an isolated database")

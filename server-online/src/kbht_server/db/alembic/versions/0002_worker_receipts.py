"""Durable per-consumer acknowledgement; preserves the original core revision."""

from pathlib import Path

from alembic import op

revision = "0002_worker_receipts"
down_revision = "0001_core"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.get_bind().exec_driver_sql(Path(__file__).with_suffix(".sql").read_text(encoding="ascii"))


def downgrade() -> None:
    raise RuntimeError("Destructive downgrade disabled; restore into an isolated database")

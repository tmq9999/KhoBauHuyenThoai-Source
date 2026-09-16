"""Leased outbox delivery state and bounded retry metadata."""

from pathlib import Path
from alembic import op

revision = "0006_outbox_delivery"
down_revision = "0005_runtime_guards"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.get_bind().exec_driver_sql(Path(__file__).with_suffix(".sql").read_text(encoding="ascii"))


def downgrade() -> None:
    raise RuntimeError("Destructive downgrade disabled; restore into an isolated database")

"""Frozen core transaction schema. Never import mutable application metadata."""

from pathlib import Path

from alembic import op

revision = "0001_core"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    folder = Path(__file__).parent
    for filename in ("0001_tables.sql", "0001_guards.sql"):
        op.get_bind().exec_driver_sql((folder / filename).read_text(encoding="ascii"))


def downgrade() -> None:
    raise RuntimeError("Destructive downgrade disabled; restore into an isolated database")

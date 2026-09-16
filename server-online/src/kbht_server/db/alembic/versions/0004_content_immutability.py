"""Prevent reverting published content to draft to bypass definition guards."""

from pathlib import Path

from alembic import op

revision = "0004_content_immutability"
down_revision = "0003_inventory_rewards"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.get_bind().exec_driver_sql(Path(__file__).with_suffix(".sql").read_text(encoding="ascii"))


def downgrade() -> None:
    raise RuntimeError("Destructive downgrade disabled; restore into an isolated database")

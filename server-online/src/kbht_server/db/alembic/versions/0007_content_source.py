"""Store verified APK content imports as immutable staged releases."""
from pathlib import Path
from alembic import op
revision = "0007_content_source"
down_revision = "0006_outbox_delivery"
branch_labels = None
depends_on = None
def upgrade() -> None:
    op.get_bind().exec_driver_sql(Path(__file__).with_suffix(".sql").read_text(encoding="ascii"))
def downgrade() -> None:
    raise RuntimeError("Destructive downgrade disabled; restore an isolated database")

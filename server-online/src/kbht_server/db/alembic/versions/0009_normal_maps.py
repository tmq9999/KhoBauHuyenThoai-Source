"""Chapter provenance and version-scoped normal map projections."""
from pathlib import Path
from alembic import op

revision = "0009_normal_maps"
down_revision = "0008_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.get_bind().exec_driver_sql(Path(__file__).with_suffix(".sql").read_text(encoding="ascii"))


def downgrade() -> None:
    raise RuntimeError("Destructive downgrade disabled; restore an isolated database")

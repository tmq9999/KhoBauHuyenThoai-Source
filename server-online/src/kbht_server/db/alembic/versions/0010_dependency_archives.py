"""Retain dependency source cells and audit blockers, not published rules."""
from pathlib import Path
from alembic import op

revision = '0010_dependency_archives'
down_revision = '0009_normal_maps'
branch_labels = None
depends_on = None


def upgrade():
    op.get_bind().exec_driver_sql(Path(__file__).with_suffix('.sql').read_text(encoding='ascii'))


def downgrade():
    raise RuntimeError('Destructive downgrade disabled; restore an isolated database')

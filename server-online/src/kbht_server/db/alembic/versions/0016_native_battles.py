"""Immutable native battle snapshots, reports and daily attempt counters."""
from pathlib import Path
from alembic import op
revision = '0016_native_battles'
down_revision = '0015_native_tutorial'
branch_labels = None
depends_on = None


def upgrade():
    op.get_bind().exec_driver_sql(Path(__file__).with_suffix('.sql').read_text(encoding='ascii'))


def downgrade():
    raise RuntimeError('Destructive downgrade disabled; restore an isolated database')

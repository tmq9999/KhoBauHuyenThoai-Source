"""Normalized native player ownership and immutable starter definitions."""
from pathlib import Path
from alembic import op

revision = '0014_native_players'
down_revision = '0013_account_status'
branch_labels = None
depends_on = None


def upgrade():
    op.get_bind().exec_driver_sql(Path(__file__).with_suffix('.sql').read_text(encoding='ascii'))


def downgrade():
    raise RuntimeError('Destructive downgrade disabled; restore an isolated database')

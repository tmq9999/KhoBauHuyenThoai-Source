"""Immutable deterministic tutorial content and append-only role issuance."""
from pathlib import Path
from alembic import op

revision = '0015_native_tutorial'
down_revision = '0014_native_players'
branch_labels = None
depends_on = None


def upgrade():
    op.get_bind().exec_driver_sql(Path(__file__).with_suffix('.sql').read_text(encoding='ascii'))


def downgrade():
    raise RuntimeError('Destructive downgrade disabled; restore an isolated database')

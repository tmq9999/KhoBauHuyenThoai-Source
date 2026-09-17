"""Isolated equipment content drafts and relational ingredient references."""
from pathlib import Path
from alembic import op

revision='0011_equipment_content'
down_revision='0010_dependency_archives'
branch_labels=None
depends_on=None


def upgrade():
    op.get_bind().exec_driver_sql(Path(__file__).with_suffix('.sql').read_text(encoding='ascii'))


def downgrade():
    raise RuntimeError('Destructive downgrade disabled; restore an isolated database')

"""Add account lock status without rewriting password or session history."""
from alembic import op

revision = '0013_account_status'
down_revision = '0012_fixed_boxes'
branch_labels = None
depends_on = None


def upgrade():
    op.get_bind().exec_driver_sql("ALTER TABLE accounts ADD COLUMN status varchar(16) NOT NULL DEFAULT 'ACTIVE', ADD CONSTRAINT ck_accounts_status CHECK (status IN ('ACTIVE','LOCKED'))")


def downgrade():
    raise RuntimeError('Destructive downgrade disabled; restore an isolated database')

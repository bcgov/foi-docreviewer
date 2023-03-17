"""empty message

Revision ID: b4b3356e00e2
Revises: 118f76cb5ead
Create Date: 2023-03-16 10:51:58.771518

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b4b3356e00e2'
down_revision = '118f76cb5ead'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column('Documents', 'incompatible', nullable=False,server_default=sa.sql.false() )


def downgrade():
    op.alter_column('Documents', 'incompatible', nullable=True)

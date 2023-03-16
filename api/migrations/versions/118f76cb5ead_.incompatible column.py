"""added incompatible column to Documents

Revision ID: 118f76cb5ead
Revises: 641ae620392d
Create Date: 2023-03-14 13:09:29.993716

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '118f76cb5ead'
down_revision = '641ae620392d'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('Documents', sa.Column('incompatible', sa.Boolean, unique=False, nullable=True, default=False))


def downgrade():
    op.drop_column('Documents', 'incompatible')

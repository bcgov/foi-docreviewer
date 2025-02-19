"""Adding boolean column to capture SOLR delete

Revision ID: 828d870c000f
Revises: 374a9a0b07e8
Create Date: 2025-01-13 15:13:45.482279

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '828d870c000f'
down_revision = '374a9a0b07e8'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('DocumentDeleted', sa.Column('removedfromsolr', sa.Boolean(), nullable=True, server_default=sa.false()))


def downgrade():
    op.drop_column('DocumentDeleted', 'removedfromsolr')

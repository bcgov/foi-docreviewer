"""Add new column to Documents table (is_searchable_pdf)

Revision ID: 1cd7be974c11
Revises: 3ab3c837fc93
Create Date: 2025-05-06 14:08:24.489824

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1cd7be974c11'
down_revision = '3ab3c837fc93'
branch_labels = None
depends_on = None


def upgrade():
   op.add_column('Documents', sa.Column('is_searchable_pdf', sa.Boolean(), nullable=True))

def downgrade():
    op.drop_column('Documents', 'is_searchable_pdf')

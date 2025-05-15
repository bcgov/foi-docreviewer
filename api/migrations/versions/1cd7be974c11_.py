"""Add new column to Documents table (needs_ocr)

Revision ID: 1cd7be974c11
Revises: db37962dca5b
Create Date: 2025-05-06 14:08:24.489824

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1cd7be974c11'
down_revision = 'db37962dca5b'
branch_labels = None
depends_on = None


def upgrade():
   op.add_column('Documents', sa.Column('needs_ocr', sa.Boolean(), nullable=True))

def downgrade():
    op.drop_column('Documents', 'needs_ocr')

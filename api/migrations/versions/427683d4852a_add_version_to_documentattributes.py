"""add version to documentattributes

Revision ID: 427683d4852a
Revises: a5254d701e1f
Create Date: 2023-06-14 22:40:36.220059

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '427683d4852a'
down_revision = 'a5254d701e1f'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('DocumentAttributes', sa.Column('version', sa.Integer, unique=False, nullable=True, default=1))
    op.add_column('DocumentAttributes', sa.Column('updatedby', sa.JSON, unique=False, nullable=True))
    op.add_column('DocumentAttributes', sa.Column('updated_at', sa.DateTime, unique=False, nullable=True))
    op.add_column('DocumentAttributes', sa.Column('isactive', sa.Boolean, unique=False, nullable=True, default=True))
    op.execute('UPDATE public."DocumentAttributes" SET version=1;')
    op.execute('UPDATE public."DocumentAttributes" SET isactive=True;')
    op.alter_column('DocumentAttributes', 'version', nullable=False)
    op.alter_column('DocumentAttributes', 'isactive', nullable=False)

def downgrade():
    op.drop_column('DocumentAttributes', 'version')
    op.drop_column('DocumentAttributes', 'updatedby')
    op.drop_column('DocumentAttributes', 'updated_at')
    op.drop_column('DocumentAttributes', 'isactive')

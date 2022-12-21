"""empty message

Revision ID: 92764562d406
Revises: ea32c62c8f0f
Create Date: 2022-12-20 13:45:40.663983

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime


# revision identifiers, used by Alembic.
revision = '92764562d406'
down_revision = 'ea32c62c8f0f'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('DocumentDeleted',
        sa.Column('documentdeletedid', sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column('filepath', sa.String(500), nullable=False),
        sa.Column('deleted', sa.Boolean, nullable=False, default=False),
        sa.Column('createdby', sa.String(length=120), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True, default=datetime.now),
        sa.Column('updatedby', sa.String(length=120), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('documentdeletedid')
    )


def downgrade():
    op.drop_table('DocumentDeleted')

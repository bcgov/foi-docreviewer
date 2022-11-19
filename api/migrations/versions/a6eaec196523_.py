"""empty message

Revision ID: a6eaec196523
Revises: b96f3a390985
Create Date: 2022-11-18 15:16:21.042354

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime

# revision identifiers, used by Alembic.
revision = 'a6eaec196523'
down_revision = 'b96f3a390985'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('DocumentHashCodes',
        sa.Column('documentid', sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column('rank1hash', sa.Text, nullable=False), 
        sa.Column('rank2hash', sa.Text, nullable=True),       
        sa.Column('created_at', sa.DateTime(), nullable=False, default=datetime.now()),
        sa.PrimaryKeyConstraint('documentid')
    )


def downgrade():
     op.drop_table('DocumentHashCodes')
